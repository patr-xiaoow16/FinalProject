"""
年报分析 Agent 工具函数
每个工具负责生成报告的一个章节
"""

import logging
import re
from typing import Dict, Any, List, Optional, Annotated
import time
from llama_index.core.tools import FunctionTool, QueryEngineTool
from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from models.report_models import (
    FinancialReview,
    BusinessGuidance,
    BusinessHighlights,
    ProfitForecastAndValuation,
    BusinessHighlight,
    FinancialStatementTable,
    FinancialStatementTables
)
from agents.visualization_agent import generate_visualization_for_query
# 相关性、因子分析已改为 LLM 生成，见 _llm_correlation_analysis / _llm_factor_analysis（多元回归已移除）

logger = logging.getLogger(__name__)

# 简单内存缓存：避免重复点击时反复执行耗时步骤（按公司+年份）
_STRATEGY_REPORT_CACHE: Dict[str, Dict[str, Any]] = {}
_STRATEGY_CACHE_TTL_SECONDS = 60 * 60 * 6  # 6小时


def _strategy_cache_key(company_name: str, year: str) -> str:
    return f"{company_name.strip()}::{str(year).strip()}"


def _get_cached_strategy_report(company_name: str, year: str, report_type: str) -> Optional[str]:
    key = _strategy_cache_key(company_name, year)
    bucket = _STRATEGY_REPORT_CACHE.get(key) or {}
    record = bucket.get(report_type)
    if not isinstance(record, dict):
        return None
    ts = record.get("ts")
    content = record.get("content")
    if not isinstance(content, str) or not content.strip():
        return None
    if not isinstance(ts, (int, float)) or (time.time() - ts) > _STRATEGY_CACHE_TTL_SECONDS:
        return None
    return content


def _set_cached_strategy_report(company_name: str, year: str, report_type: str, content: str) -> None:
    if not isinstance(content, str) or not content.strip():
        return
    key = _strategy_cache_key(company_name, year)
    if key not in _STRATEGY_REPORT_CACHE:
        _STRATEGY_REPORT_CACHE[key] = {}
    _STRATEGY_REPORT_CACHE[key][report_type] = {
        "content": content.strip(),
        "ts": time.time()
    }


async def _generate_card_insight(llm: Any, context: str, card_type: str) -> str:
    """
    用 LLM 二次生成可视化卡片的数据洞察，限制字数（非截断）。
    context: 已有分析结论或数据摘要
    card_type: 如 "相关性分析"、"因子分析"、"聚类分析"
    返回不超过 80 字的概括文本。
    """
    if not (context and str(context).strip()):
        return ""
    import re
    prompt = f"""以下为{card_type}的分析结论或数据摘要。请用1至2句话概括其核心要点，用于展示在可视化卡片下方。
**严格要求**：总字数不超过80字。请直接生成80字以内的完整句子，不要先写长文再截断，不要使用省略号。
直接输出概括文本，不要标题、不要编号、不要引号、不要「概括：」等前缀。

内容摘要：
{str(context).strip()[:2000]}
"""
    try:
        resp = await llm.achat([
            ChatMessage(role="system", content="你是投资分析师助手。按要求输出简短概括，严格控制在80字以内。"),
            ChatMessage(role="user", content=prompt)
        ])
        content = resp.message.content if hasattr(resp, "message") and hasattr(resp.message, "content") else str(resp)
        text = (content or "").strip()
        text = re.sub(r"^[概括：\s]+", "", text)
        text = re.sub(r"^[\"']|[\"']$", "", text)
        # 不截断：要求 LLM 在 80 字内完成；若仍超长仅做安全截断（100 字）
        if len(text) > 100:
            text = text[:97] + "…"
        return text.strip()
    except Exception as e:
        logger.warning(f"卡片洞察生成失败 ({card_type}): {e}")
        return ""


def _create_default_financial_review(
    company_name: str,
    year: str,
    parsed_data: Optional[Dict],
    balance_sheet_data: str,
    income_statement_data: str,
    cash_flow_data: str
) -> FinancialReview:
    """
    创建默认的FinancialReview结构，当JSON解析或验证失败时使用
    
    Args:
        company_name: 公司名称
        year: 年份
        parsed_data: 部分解析的数据（如果有）
        balance_sheet_data: 资产负债表数据
        income_statement_data: 利润表数据
        cash_flow_data: 现金流量表数据
    
    Returns:
        FinancialReview对象
    """
    def _build_default_table(title: str, metric_names: List[str]) -> FinancialStatementTable:
        table_years = [year]
        if year.isdigit():
            prev_year = str(int(year) - 1)
            table_years.append(prev_year)
        headers = ["指标"] + table_years + ["同比变动"]
        rows = []
        for metric in metric_names:
            rows.append([metric] + ["/" for _ in table_years] + ["/"])
        return FinancialStatementTable(title=title, headers=headers, rows=rows, insight="未生成洞察")

    visualization_tables = FinancialStatementTables(
        balance_sheet_assets=_build_default_table(
            "资产结构表",
            [
                "资产总额",
                "发放贷款及垫款",
                "个人贷款",
                "企业贷款",
                "投资类金融资产",
                "现金及存放央行款项",
                "存放同业款项"
            ]
        ),
        balance_sheet_liabilities=_build_default_table(
            "负债结构表",
            [
                "负债总额",
                "吸收存款",
                "个人存款",
                "企业存款",
                "向央行借款",
                "同业负债",
                "已发行债务证券",
                "卖出回购金融资产"
            ]
        ),
        income_statement_revenue=_build_default_table(
            "营业收入结构表",
            [
                "营业收入合计",
                "利息净收入",
                "非利息净收入",
                "手续费及佣金净收入",
                "其他非利息净收入",
                "投资收益",
                "公允价值变动损益"
            ]
        ),
        income_statement_expense=_build_default_table(
            "营业支出结构表",
            [
                "营业支出合计",
                "业务及管理费",
                "信用及其他资产减值损失",
                "税金及附加"
            ]
        ),
        cash_flow=_build_default_table(
            "现金流量明细",
            [
                "经营活动现金流",
                "投资活动现金流",
                "筹资活动现金流",
                "现金净变动额"
            ]
        )
    )

    summary = (
        f"基于提供的数据，{company_name} {year}年的财务表现需要进一步核验。"
        f"资产负债表数据：{balance_sheet_data[:200]}..."
        f"利润表数据：{income_statement_data[:200]}..."
        f"现金流量表数据：{cash_flow_data[:200]}..."
    )

    return FinancialReview(summary=summary, visualization_tables=visualization_tables)


def _validate_and_clean_data(data: Dict[str, Any], model_class) -> Dict[str, Any]:
    """
    验证和清理数据，确保符合模型要求
    
    Args:
        data: 原始数据字典
        model_class: Pydantic模型类
    
    Returns:
        清理后的数据字典
    """
    if not isinstance(data, dict):
        return data
    
    try:
        # 尝试用模型验证数据
        validated = model_class(**data)
        return validated.model_dump()
    except Exception as e:
        logger.warning(f"数据验证失败，尝试清理: {str(e)}")
        # 如果验证失败，尝试清理常见问题
        cleaned = {}
        for key, value in data.items():
            # 跳过错误字段
            if key == "error":
                continue
            # 清理空值
            if value is None or value == "":
                continue
            # 清理无效的字符串
            if isinstance(value, str) and value.strip() == "":
                continue
            cleaned[key] = value
        return cleaned


# ==================== 数据检索工具 ====================

def create_query_engine_tool(query_engine, name: str, description: str) -> QueryEngineTool:
    """
    创建查询引擎工具
    
    Args:
        query_engine: LlamaIndex 查询引擎
        name: 工具名称
        description: 工具描述
    
    Returns:
        QueryEngineTool 实例
    """
    return QueryEngineTool.from_defaults(
        query_engine=query_engine,
        name=name,
        description=description
    )


# ==================== 财务数据检索工具 ====================

def retrieve_financial_data(
    company_name: Annotated[str, "公司名称"],
    year: Annotated[str, "年份,如'2023'"],
    metric_type: Annotated[str, "指标类型: balance_sheet_detailed, income_statement_detailed, cash_flow_detailed 等"],
    query_engine: Any
) -> str:
    """
    检索财务数据
    
    从年报中检索特定的财务指标数据
    
    Args:
        company_name: 公司名称
        year: 年份
        metric_type: 指标类型
        query_engine: 查询引擎
    
    Returns:
        财务数据的文本描述
    """
    import time
    retrieval_start = time.time()
    try:
        logger.debug(f"🔍 [retrieve_financial_data] 开始检索: {company_name} {year}年 {metric_type}")
        # 构建查询
        query_map = {
            "balance_sheet_detailed": (
                f"{company_name} {year}年 资产负债表 "
                "资产总额 发放贷款及垫款 个人贷款 企业贷款 投资类金融资产 "
                "现金及存放央行款项 存放同业款项 "
                "负债总额 吸收存款 个人存款 企业存款 向央行借款 同业负债 "
                "已发行债务证券 卖出回购金融资产"
            ),
            "income_statement_detailed": (
                f"{company_name} {year}年 利润表 "
                "营业收入合计 利息净收入 非利息净收入 手续费及佣金净收入 "
                "其他非利息净收入 投资收益 公允价值变动损益 "
                "营业支出合计 业务及管理费 信用及其他资产减值损失 税金及附加"
            ),
            "cash_flow_detailed": (
                f"{company_name} {year}年 现金流量表 "
                "经营活动现金流 投资活动现金流 筹资活动现金流 现金净变动额"
            )
        }
        
        query = query_map.get(metric_type, f"{company_name} {year}年 {metric_type}")
        
        # 执行查询 - 处理同步和异步两种情况
        try:
            # 尝试同步查询
            if hasattr(query_engine, 'query'):
                response = query_engine.query(query)
            else:
                # 如果query_engine是RAGEngine，使用其query方法
                if hasattr(query_engine, 'query'):
                    response = query_engine.query(query)
                else:
                    raise ValueError("query_engine 不支持 query 方法")
            
            # 提取响应内容
            if hasattr(response, 'response'):
                # Response对象，提取response属性
                content = str(response.response)
            elif hasattr(response, 'message'):
                # 有message属性
                if hasattr(response.message, 'content'):
                    content = str(response.message.content)
                else:
                    content = str(response.message)
            elif hasattr(response, 'content'):
                # 直接有content属性
                content = str(response.content)
            elif isinstance(response, dict):
                # 字典类型，提取answer或content
                content = response.get('answer', response.get('content', str(response)))
            else:
                # 其他类型，直接转换为字符串
                content = str(response)
            
            retrieval_time = time.time() - retrieval_start
            if retrieval_time > 30.0:
                logger.warning(f"⚠️ [retrieve_financial_data] {metric_type} 检索耗时过长: {retrieval_time:.2f}秒")
            else:
                logger.info(f"✅ [retrieve_financial_data] 检索财务数据成功: {metric_type}，耗时: {retrieval_time:.2f}秒")
            return content if content else f"未找到{metric_type}相关数据"
            
        except Exception as query_error:
            retrieval_time = time.time() - retrieval_start
            logger.error(f"❌ [retrieve_financial_data] 查询执行失败（耗时: {retrieval_time:.2f}秒）: {str(query_error)}")
            logger.error(f"[retrieve_financial_data] 错误类型: {type(query_error).__name__}")
            import traceback
            logger.error(f"[retrieve_financial_data] 错误堆栈:\n{traceback.format_exc()}")
            return f"检索失败（{metric_type}）: {str(query_error)}"
        
    except Exception as e:
        retrieval_time = time.time() - retrieval_start if 'retrieval_start' in locals() else 0
        logger.error(f"❌ [retrieve_financial_data] 检索财务数据异常（耗时: {retrieval_time:.2f}秒）: {str(e)}")
        logger.error(f"[retrieve_financial_data] 错误类型: {type(e).__name__}")
        import traceback
        logger.error(f"[retrieve_financial_data] 错误堆栈:\n{traceback.format_exc()}")(f"❌ 检索财务数据失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return f"检索失败: {str(e)}"


def retrieve_business_data(
    company_name: Annotated[str, "公司名称"],
    year: Annotated[str, "年份"],
    business_type: Annotated[str, "业务类型,如'主营业务'、'分部业务'、'产品业务'"],
    query_engine: Any
) -> str:
    """
    检索业务数据
    
    从年报中检索业务相关信息
    
    Args:
        company_name: 公司名称
        year: 年份
        business_type: 业务类型
        query_engine: 查询引擎
    
    Returns:
        业务数据的文本描述
    """
    try:
        query = f"{company_name} {year}年 {business_type} 业务收入 业务增长 市场份额"
        
        # 执行查询 - 处理同步和异步两种情况
        try:
            if hasattr(query_engine, 'query'):
                response = query_engine.query(query)
            else:
                raise ValueError("query_engine 不支持 query 方法")
            
            # 提取响应内容
            if hasattr(response, 'response'):
                content = str(response.response)
            elif hasattr(response, 'message'):
                if hasattr(response.message, 'content'):
                    content = str(response.message.content)
                else:
                    content = str(response.message)
            elif hasattr(response, 'content'):
                content = str(response.content)
            elif isinstance(response, dict):
                content = response.get('answer', response.get('content', str(response)))
            else:
                content = str(response)
            
            logger.info(f"✅ 检索业务数据成功: {business_type}")
            return content if content else f"未找到{business_type}相关数据"
            
        except Exception as query_error:
            logger.error(f"❌ 查询执行失败: {str(query_error)}")
            import traceback
            logger.error(traceback.format_exc())
            return f"检索失败: {str(query_error)}"
        
    except Exception as e:
        logger.error(f"❌ 检索业务数据失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return f"检索失败: {str(e)}"


# ==================== 章节生成工具 ====================
# 财务点评
async def generate_financial_review(
    company_name: Annotated[str, "公司名称"],
    year: Annotated[str, "年份,如'2023'"],
    query_engine: Any
) -> Dict[str, Any]:
    """
    生成财务点评章节
    
    包括:
    1. 财务点评总结
    2. 财务报表可视化表格
    
    Args:
        company_name: 公司名称
        year: 年份
        query_engine: 查询引擎
    
    Returns:
        财务点评的结构化数据（总结 + 表格）
    """
    import time
    tool_start_time = time.time()
    try:
        logger.info(f"🔧 [generate_financial_review] 开始生成财务点评: {company_name} {year}年")
        
        # 1. 检索财务报表数据 - 添加性能监控
        data_retrieval_start = time.time()
        try:
            balance_sheet_data = retrieve_financial_data(company_name, year, "balance_sheet_detailed", query_engine)
            balance_sheet_time = time.time() - data_retrieval_start
            logger.info(f"✅ [generate_financial_review] 资产负债表数据检索完成，耗时: {balance_sheet_time:.2f}秒")
            
            income_statement_start = time.time()
            income_statement_data = retrieve_financial_data(company_name, year, "income_statement_detailed", query_engine)
            income_statement_time = time.time() - income_statement_start
            logger.info(f"✅ [generate_financial_review] 利润表数据检索完成，耗时: {income_statement_time:.2f}秒")
            
            cashflow_start = time.time()
            cash_flow_data = retrieve_financial_data(company_name, year, "cash_flow_detailed", query_engine)
            cashflow_time = time.time() - cashflow_start
            logger.info(f"✅ [generate_financial_review] 现金流数据检索完成，耗时: {cashflow_time:.2f}秒")
            
            total_retrieval_time = time.time() - data_retrieval_start
            if total_retrieval_time > 60.0:
                logger.warning(f"⚠️ [generate_financial_review] 数据检索总耗时过长: {total_retrieval_time:.2f}秒")
        except Exception as retrieval_error:
            retrieval_time = time.time() - data_retrieval_start
            logger.error(f"❌ [generate_financial_review] 数据检索失败（耗时: {retrieval_time:.2f}秒）: {str(retrieval_error)}")
            raise Exception(f"数据检索阶段失败: {str(retrieval_error)}")
        
        # 2. 使用 LLM 生成结构化的财务点评 - 添加性能监控
        llm_generation_start = time.time()
        llm = Settings.llm

        prompt = f"""
作为资深财务分析师，请基于以下财务数据，生成{company_name} {year}年度的财务点评总结，并构建可视化表格视图。

## 数据来源
以下数据均来自{company_name} {year}年度年报：

### 资产负债表数据
{balance_sheet_data}

### 利润表数据
{income_statement_data}

### 现金流数据
{cash_flow_data}

## 分析要求
请生成结构化的财务点评，要求如下：

### 1. 财务点评总结
你是一名专业的财务分析师，请基于我提供的资产负债表、利润表和现金流量表数据，
分别对三张表进行一句话总结，并给出一个综合三表的总体判断。

分析要求如下：

一、资产负债表分析（一句话）
请从以下三个角度综合判断：
1. 资产结构：公司的资产主要由什么构成？（如现金、存货、固定资产、金融资产等）
2. 偿债风险：结合资产负债率，判断杠杆水平是否偏高或可控
3. 实力基础：所有者权益规模及变化趋势，反映公司的“家底”是否稳健

要求：
- 用一句完整的话给出判断
- 以“结构 + 风险 + 实力”为主线
- 不逐项罗列数据，不引入未给出的指标
- 句末补充2个关键数据点（指标名+数值/同比），用“（证据：...）”标注
- 长度控制在45-55字

输出格式：
资产负债表：XXXXXX

二、利润表分析（一句话）
请从以下三个角度综合判断：
1. 趋势：收入和净利润是增长还是下滑，变化是否一致
2. 盈利能力：毛利率、净利率水平是否合理（仅基于已给数据，不强行对比行业）
3. 利润质量：利润主要来自主营业务还是依赖非经常性项目（如资产处置、投资收益）

要求：
- 用一句话概括“赚不赚钱 + 靠什么赚”
- 如果存在利润质量隐忧，请用委婉提示而非直接否定
- 句末补充2个关键数据点（指标名+数值/同比），用“（证据：...）”标注
- 长度控制在45-55字

输出格式：
利润表：XXXXXX

三、现金流量表分析（一句话）
请重点遵循以下原则：
1. 黄金法则：经营活动现金流是否为正，是否具备覆盖投资和分红还债的能力
2. 伪盈利识别：若利润为正但经营现金流长期为负，需明确指出风险

要求：
- 用一句话判断“钱是否真的赚到”
- 明确现金流对利润结论的支持或否定关系
- 句末补充2个关键数据点（指标名+数值/同比），用“（证据：...）”标注
- 长度控制在45-55字

输出格式：
现金流量表：XXXXXX

四、综合三表总结（一句话）
请结合三张表，从以下角度给出总体判断：
- 公司的经营状态是健康、承压，还是处于调整期
- 利润是否有现金支撑
- 资产结构与盈利模式是否匹配

要求：
- 给出一个“整体画像式”的判断
- 不重复前三句话的表述
- 偏向风险与稳健性的综合评价
- 句末补充2个关键数据点（指标名+数值/同比），用“（证据：...）”标注
- 长度控制在45-55字

输出格式：
综合判断：XXXXXX

注意事项：
- 只基于提供的数据进行分析，不进行数据假设
- 不输出计算过程、不展示公式
- 每一句话控制在 20–50 字以内

### 2. 可视化表格视图（必须输出）
请基于资产负债表、利润表、现金流量表构建如下表格：

#### 资产负债表
- 资产结构表（指标）：资产总额、发放贷款及垫款、个人贷款、企业贷款、投资类金融资产、现金及存放央行款项、存放同业款项
- 负债结构表（指标）：负债总额、吸收存款、个人存款、企业存款、向央行借款、同业负债、已发行债务证券、卖出回购金融资产

#### 利润表
- 营业收入结构表（指标）：营业收入合计、利息净收入、非利息净收入、手续费及佣金净收入、其他非利息净收入、投资收益、公允价值变动损益
- 营业支出结构表（指标）：营业支出合计、业务及管理费、信用及其他资产减值损失、税金及附加

#### 现金流量表
- 现金流量明细（指标）：经营活动现金流、投资活动现金流、筹资活动现金流、现金净变动额

### 表格输出规范
- 表头必须包含：指标、年份（不同年份的数据）、同比变动
- 年份列优先使用{year}和{str(int(year) - 1) if year.isdigit() else year}；如无法获取上一年数据，使用"/"
- 没有检索到的数据用"/"
- 同比变动如无法计算或缺失，使用"/"

### 表格洞察要求（每表一句话）
你将为财务报表分析生成“一表一句话”的极简结论。写法严格遵循：
1) 先点出结构/主项（只提1-2个）
2) 再点出同比变化方向（只提1-2个关键变化）
3) 最后给出判断（战略/对冲/真实性），不引入文档外指标
4) 每句话长度控制在 35-50 字
5) 必须在句末给出 2-3 个证据点（指标名+同比/占比）

分别生成以下五张子表的结论：
A 资产结构表：围绕“零售降、对公升、投资补位/流动性管理”
B 负债结构表：围绕“存款为核心、压降央行借款/高成本负债、回购调节”
C 营业收入结构表：围绕“利息净收入拖累、非息对冲、对冲来自其他非息/投资收益”
D 营业支出结构表：围绕“费用+减值下降对冲收入下滑”，并追加一句“减值下降可能源于主动少提”的风险提示（若impairment_yoy<0）
E 现金流量明细表：围绕“CFO为正但收缩；投资/筹资反映战略布局；现金储备变化”

## ⚠️ 严格输出要求（必须遵守）
你必须输出一个有效的JSON对象，且仅输出JSON，不要有任何其他文字说明。

### JSON格式要求：
1. 必须是有效的JSON格式，可以直接被JSON.parse()解析
2. 不要使用markdown代码块（不要用```json包裹）
3. 不要有任何前缀或后缀文字
4. 直接输出JSON对象，从{{开始，以}}结束
5. 所有字符串值必须用双引号包裹
6. 所有数字和布尔值不要用引号
7. 确保所有必需字段都存在

### JSON结构（必须严格遵循）：
{{
  "summary": "财务点评总结文字",
  "visualization_tables": {{
    "balance_sheet_assets": {{
      "title": "资产结构表",
      "headers": ["指标", "{year}", "{str(int(year) - 1) if year.isdigit() else year}", "同比变动"],
      "insight": "- 资产结构表洞察：一句话结论（证据：..., ..., ...）",
      "rows": [
        ["资产总额", "数值", "数值", "同比变动"],
        ["发放贷款及垫款", "数值", "数值", "同比变动"]
      ]
    }},
    "balance_sheet_liabilities": {{
      "title": "负债结构表",
      "headers": ["指标", "{year}", "{str(int(year) - 1) if year.isdigit() else year}", "同比变动"],
      "insight": "- 负债结构表洞察：一句话结论（证据：..., ..., ...）",
      "rows": [
        ["负债总额", "数值", "数值", "同比变动"]
      ]
    }},
    "income_statement_revenue": {{
      "title": "营业收入结构表",
      "headers": ["指标", "{year}", "{str(int(year) - 1) if year.isdigit() else year}", "同比变动"],
      "insight": "- 营业收入结构表洞察：一句话结论（证据：..., ..., ...）",
      "rows": [
        ["营业收入合计", "数值", "数值", "同比变动"]
      ]
    }},
    "income_statement_expense": {{
      "title": "营业支出结构表",
      "headers": ["指标", "{year}", "{str(int(year) - 1) if year.isdigit() else year}", "同比变动"],
      "insight": "- 营业支出结构表洞察：一句话结论（证据：..., ..., ...）",
      "rows": [
        ["营业支出合计", "数值", "数值", "同比变动"]
      ]
    }},
    "cash_flow": {{
      "title": "现金流量明细",
      "headers": ["指标", "{year}", "{str(int(year) - 1) if year.isdigit() else year}", "同比变动"],
      "insight": "- 现金流量明细表洞察：一句话结论（证据：..., ..., ...）",
      "rows": [
        ["经营活动现金流", "数值", "数值", "同比变动"]
      ]
    }}
  }}
}}

### 重要提示：
- 如果某些数据缺失，使用合理的默认值（如"数据缺失"、"暂无数据"等）
- 所有字段都必须存在，不能为null
- 数组字段至少包含一个元素
- 直接输出上述JSON结构，不要有任何其他内容
"""

        # 使用结构化输出 - 添加异常处理和性能监控
        response = None
        structured_llm_start = time.time()
        try:
            sllm = llm.as_structured_llm(FinancialReview)
            raw_response = await sllm.achat([
                ChatMessage(role="system", content="你是一个专业的财务分析师,擅长分析年报数据。你必须严格按照用户要求的JSON格式输出，只输出JSON，不要有任何其他文字。"),
                ChatMessage(role="user", content=prompt)
            ])
            
            # 调试：输出响应类型和内容（前500字符）
            logger.info(f"🔍 [generate_financial_review] 响应类型: {type(raw_response).__name__}")
            if hasattr(raw_response, '__dict__'):
                logger.info(f"🔍 [generate_financial_review] 响应属性: {list(raw_response.__dict__.keys())}")
            if isinstance(raw_response, str):
                logger.info(f"🔍 [generate_financial_review] 响应内容（前500字符）: {raw_response[:500]}")
            elif hasattr(raw_response, 'message'):
                logger.info(f"🔍 [generate_financial_review] response.message类型: {type(raw_response.message).__name__}")
                if hasattr(raw_response.message, 'content'):
                    content_preview = str(raw_response.message.content)[:500] if raw_response.message.content else "None"
                    logger.info(f"🔍 [generate_financial_review] message.content（前500字符）: {content_preview}")
            
            # 检查响应类型 - LlamaIndex有时返回字符串而不是Pydantic模型
            if isinstance(raw_response, str):
                logger.warning(f"⚠️ [generate_financial_review] 结构化LLM返回字符串而非模型对象，尝试解析JSON")
                # 直接处理字符串响应
                import json
                import re
                json_match = re.search(r'\{[\s\S]*\}', raw_response)
                if json_match:
                    json_str = json_match.group(0)
                    parsed_data = json.loads(json_str)
                    # 处理嵌套结构
                    if 'financial_review' in parsed_data:
                        parsed_data = parsed_data['financial_review']
                    elif 'charts' not in parsed_data and len(parsed_data) == 1:
                        parsed_data = list(parsed_data.values())[0]
                    try:
                        response = FinancialReview(**parsed_data)
                        structured_llm_time = time.time() - structured_llm_start
                        logger.info(f"✅ [generate_financial_review] 从字符串解析JSON成功，耗时: {structured_llm_time:.2f}秒")
                    except Exception as parse_error:
                        logger.warning(f"⚠️ [generate_financial_review] JSON解析失败: {str(parse_error)}")
                        raise Exception(f"无法从字符串响应解析JSON: {str(parse_error)}")
                else:
                    raise ValueError("响应是字符串但无法提取JSON")
            elif isinstance(raw_response, FinancialReview):
                # 已经是Pydantic模型
                response = raw_response
                structured_llm_time = time.time() - structured_llm_start
                logger.info(f"✅ [generate_financial_review] 结构化输出成功，耗时: {structured_llm_time:.2f}秒")
            elif hasattr(raw_response, 'message'):
                # 可能是Response对象，提取message
                if hasattr(raw_response.message, 'content'):
                    content = raw_response.message.content
                    if isinstance(content, str):
                        # message.content是字符串，需要解析JSON
                        logger.warning(f"⚠️ [generate_financial_review] 响应message.content是字符串，尝试解析JSON")
                        import json
                        import re
                        json_match = re.search(r'\{[\s\S]*\}', content)
                        if json_match:
                            json_str = json_match.group(0)
                            parsed_data = json.loads(json_str)
                            # 处理嵌套结构
                            if 'financial_review' in parsed_data:
                                parsed_data = parsed_data['financial_review']
                            elif 'charts' not in parsed_data and len(parsed_data) == 1:
                                parsed_data = list(parsed_data.values())[0]
                            try:
                                response = FinancialReview(**parsed_data)
                                structured_llm_time = time.time() - structured_llm_start
                                logger.info(f"✅ [generate_financial_review] 从message.content解析JSON成功，耗时: {structured_llm_time:.2f}秒")
                            except Exception as parse_error:
                                logger.warning(f"⚠️ [generate_financial_review] message.content JSON解析失败: {str(parse_error)}")
                                raise ValueError(f"无法从message.content解析JSON: {str(parse_error)}")
                        else:
                            raise ValueError("响应message.content是字符串但无法提取JSON")
                    else:
                        # content不是字符串，可能是Pydantic模型
                        response = content
                        structured_llm_time = time.time() - structured_llm_start
                        logger.info(f"✅ [generate_financial_review] 结构化输出成功（从message.content），耗时: {structured_llm_time:.2f}秒")
                else:
                    # message没有content属性，尝试直接使用message
                    response = raw_response.message
                    structured_llm_time = time.time() - structured_llm_start
                    logger.info(f"✅ [generate_financial_review] 结构化输出成功（从message），耗时: {structured_llm_time:.2f}秒")
            else:
                # 其他类型，尝试直接使用
                # 检查是否有raw属性（LlamaIndex结构化输出的标准格式）
                if hasattr(raw_response, 'raw'):
                    logger.info(f"🔍 [generate_financial_review] 发现raw属性，类型: {type(raw_response.raw).__name__}")
                    if isinstance(raw_response.raw, FinancialReview):
                        response = raw_response.raw
                        structured_llm_time = time.time() - structured_llm_start
                        logger.info(f"✅ [generate_financial_review] 从raw属性获取Pydantic模型成功，耗时: {structured_llm_time:.2f}秒")
                    else:
                        logger.warning(f"⚠️ [generate_financial_review] raw属性不是FinancialReview类型，而是: {type(raw_response.raw).__name__}")
                        # 尝试从raw中提取
                        if hasattr(raw_response.raw, 'model_dump'):
                            try:
                                parsed_data = raw_response.raw.model_dump()
                                response = FinancialReview(**parsed_data)
                                structured_llm_time = time.time() - structured_llm_start
                                logger.info(f"✅ [generate_financial_review] 从raw.model_dump()重建模型成功，耗时: {structured_llm_time:.2f}秒")
                            except Exception as e:
                                logger.warning(f"⚠️ [generate_financial_review] 从raw重建模型失败: {str(e)}")
                                response = raw_response
                        else:
                            response = raw_response
                else:
                    response = raw_response
                structured_llm_time = time.time() - structured_llm_start
                logger.info(f"✅ [generate_financial_review] 结构化输出成功（类型: {type(response).__name__}），耗时: {structured_llm_time:.2f}秒")
            
            # 确保structured_llm_time已定义
            if 'structured_llm_time' not in locals():
                structured_llm_time = time.time() - structured_llm_start
            
            if structured_llm_time > 60.0:
                logger.warning(f"⚠️ [generate_financial_review] LLM生成耗时过长: {structured_llm_time:.2f}秒")
                
        except (AttributeError, ValueError, TypeError) as structured_error:
            error_type = type(structured_error).__name__
            error_msg = str(structured_error)
            structured_llm_time = time.time() - structured_llm_start
            
            # 更详细的错误信息
            if "model_dump_json" in error_msg or "AttributeError" in error_type:
                logger.warning(f"⚠️ [generate_financial_review] 结构化LLM返回了字符串而非Pydantic模型（耗时: {structured_llm_time:.2f}秒）")
                logger.warning(f"[generate_financial_review] 错误类型: {error_type}, 错误信息: {error_msg}")
                logger.info(f"[generate_financial_review] 这是LlamaIndex的已知问题，将尝试从字符串解析JSON")
            else:
                logger.warning(f"⚠️ [generate_financial_review] 结构化输出失败（{error_type}，耗时: {structured_llm_time:.2f}秒）: {error_msg}")
            
            logger.info(f"[generate_financial_review] 尝试使用普通LLM输出并手动解析JSON")
            # 回退到普通LLM输出，然后手动解析JSON
            try:
                normal_response = await llm.achat([
                    ChatMessage(role="system", content="你是一个专业的财务分析师,擅长分析年报数据。你必须严格按照用户要求的JSON格式输出，只输出JSON，不要有任何其他文字。"),
                    ChatMessage(role="user", content=prompt)
                ])
                
                # 提取响应内容
                if hasattr(normal_response, 'message'):
                    content = normal_response.message.content if hasattr(normal_response.message, 'content') else str(normal_response.message)
                elif hasattr(normal_response, 'content'):
                    content = normal_response.content
                else:
                    content = str(normal_response)
                
                # 尝试解析JSON
                import json
                import re
                # 提取JSON部分（可能包含markdown代码块）
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    json_str = json_match.group(0)
                    parsed_data = json.loads(json_str)
                    
                    # 处理嵌套结构（如 {'financial_review': {...}}）
                    if 'financial_review' in parsed_data:
                        parsed_data = parsed_data['financial_review']
                    elif 'charts' not in parsed_data and len(parsed_data) == 1:
                        # 如果只有一层嵌套，提取内层
                        parsed_data = list(parsed_data.values())[0]
                    
                    # 尝试构建FinancialReview对象，如果失败则生成默认值
                    try:
                        response = FinancialReview(**parsed_data)
                        logger.info(f"✅ 手动解析JSON成功")
                    except Exception as validation_error:
                        logger.warning(f"⚠️ JSON验证失败，生成默认结构: {str(validation_error)}")
                        # 生成默认的FinancialReview结构
                        response = _create_default_financial_review(
                            company_name,
                            year,
                            parsed_data,
                            balance_sheet_data,
                            income_statement_data,
                            cash_flow_data
                        )
                        logger.info(f"✅ 使用默认结构生成财务点评")
                else:
                    raise ValueError("无法从响应中提取JSON")
            except Exception as fallback_error:
                fallback_error_type = type(fallback_error).__name__
                fallback_time = time.time() - structured_llm_start
                logger.error(f"❌ [generate_financial_review] 回退方案也失败（{fallback_error_type}，总耗时: {fallback_time:.2f}秒）: {str(fallback_error)}")
                import traceback
                logger.error(f"[generate_financial_review] 回退错误堆栈:\n{traceback.format_exc()}")
                # 即使失败，也生成一个基本的响应，避免完全失败
                try:
                    response = _create_default_financial_review(
                        company_name,
                        year,
                        None,
                        balance_sheet_data,
                        income_statement_data,
                        cash_flow_data
                    )
                    final_time = time.time() - structured_llm_start
                    logger.info(f"✅ [generate_financial_review] 使用默认结构作为最终回退方案，总耗时: {final_time:.2f}秒")
                except Exception as final_error:
                    final_error_type = type(final_error).__name__
                    final_time = time.time() - structured_llm_start
                    logger.error(f"❌ [generate_financial_review] 最终回退方案也失败（{final_error_type}，总耗时: {final_time:.2f}秒）: {str(final_error)}")
                    logger.error(f"[generate_financial_review] 最终错误堆栈:\n{traceback.format_exc()}")
                    raise Exception(f"生成财务点评失败: 结构化输出失败({error_type}: {error_msg})，回退方案失败({fallback_error_type}: {str(fallback_error)})，最终回退也失败({final_error_type}: {str(final_error)})")

        total_time = time.time() - tool_start_time
        logger.info(f"✅ [generate_financial_review] 财务点评生成成功，总耗时: {total_time:.2f}秒")
        if total_time > 90.0:
            logger.warning(f"⚠️ [generate_financial_review] 工具执行总耗时过长: {total_time:.2f}秒，可能影响整体性能")
        
        # 处理响应 - 检查 response 的类型
        result_dict = None
        
        # 如果response是字典且包含error，直接返回
        if isinstance(response, dict) and 'error' in response:
            result_dict = response
        # 首先检查是否是Pydantic模型
        elif isinstance(response, FinancialReview):
            result_dict = response.model_dump()
        # 然后尝试获取 raw 属性
        elif hasattr(response, 'raw'):
            raw_data = response.raw
            # 如果是 Pydantic 模型，使用 model_dump()
            if hasattr(raw_data, 'model_dump'):
                try:
                    result_dict = raw_data.model_dump()
                except Exception as e:
                    logger.warning(f"model_dump() 失败: {e}")
            # 如果是字典，直接返回
            elif isinstance(raw_data, dict):
                result_dict = raw_data
            # 如果是字符串，尝试解析 JSON
            elif isinstance(raw_data, str):
                import json
                try:
                    result_dict = json.loads(raw_data)
                except json.JSONDecodeError:
                    logger.warning(f"无法解析字符串响应为JSON: {raw_data[:100]}")
                    result_dict = {"content": raw_data}
            else:
                # 其他类型，尝试转换为字典
                logger.warning(f"意外的响应类型: {type(raw_data)}")
                result_dict = {"content": str(raw_data)}
        
        # 如果没有 raw 属性或处理失败，尝试直接使用 response
        if result_dict is None:
            if hasattr(response, 'model_dump'):
                try:
                    result_dict = response.model_dump()
                except Exception as e:
                    logger.warning(f"response.model_dump() 失败: {e}")
            elif isinstance(response, dict):
                result_dict = response
            else:
                # 尝试转换为字符串，然后包装成字典
                result_dict = {"content": str(response)}
        
        # 确保返回的是字典格式
        if not isinstance(result_dict, dict):
            result_dict = {"content": str(result_dict)}
        
        # 添加元数据
        result_dict["company_name"] = company_name
        result_dict["year"] = year
        
        # 数据验证和清理
        result_dict = _validate_and_clean_data(result_dict, FinancialReview)
        
        return result_dict
        
    except Exception as e:
        total_time = time.time() - tool_start_time if 'tool_start_time' in locals() else 0
        error_type = type(e).__name__
        logger.error(f"❌ [generate_financial_review] 生成财务点评失败（耗时: {total_time:.2f}秒）: {str(e)}")
        logger.error(f"[generate_financial_review] 错误类型: {error_type}")
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"[generate_financial_review] 错误堆栈:\n{error_traceback}")
        
        # 提取错误位置
        error_location = "unknown"
        if "retrieval" in str(e).lower() or "数据检索" in str(e):
            error_location = "data_retrieval"
        elif "structured" in str(e).lower() or "LLM" in str(e):
            error_location = "llm_generation"
        elif "validation" in str(e).lower() or "验证" in str(e):
            error_location = "data_validation"
        elif "serialization" in str(e).lower() or "序列化" in str(e):
            error_location = "serialization"
        
        # 返回错误信息而不是抛出异常，避免中断整个流程
        return {
            "error": f"生成财务点评失败: {str(e)}",
            "error_type": error_type,
            "error_location": error_location,
            "elapsed_seconds": total_time,
            "company_name": company_name,
            "year": year
        }


async def generate_business_guidance(
    company_name: Annotated[str, "公司名称"],
    year: Annotated[str, "年份"],
    query_engine: Any
) -> Dict[str, Any]:
    """
    生成业绩指引章节
    
    包括:
    1. 业绩预告期间
    2. 预计的经营业绩
    3. 各业务的具体指引
    4. 风险提示
    
    Args:
        company_name: 公司名称
        year: 年份
        query_engine: 查询引擎
    
    Returns:
        业绩指引的结构化数据
    """
    try:
        logger.info(f"开始生成业绩指引: {company_name} {year}年")
        
        # 检索业绩指引相关数据
        query = f"{company_name} {year}年 业绩预告 业绩指引 下一年度预期 经营计划"
        guidance_data = query_engine.query(query)

        # 补充检索核心指标锚点
        key_metrics_query = (
            f"{company_name} {year}年 业绩指引 关键指标 经营指标 财务指标 "
            "营业收入 净利润 净息差 不良率 资本充足率 成本收入比"
        )
        key_metrics_data = query_engine.query(key_metrics_query)
        
        # 使用 LLM 生成结构化的业绩指引
        llm = Settings.llm

        def _extract_json_block(text: str) -> Dict[str, Any]:
            import json
            import re
            if not text:
                return {}
            json_match = re.search(r'\{[\s\S]*\}', text)
            if not json_match:
                return {}
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                return {}

        def _normalize_visualization_insights(data: Dict[str, Any]) -> Dict[str, Any]:
            if not isinstance(data, dict):
                return {}
            allowed_types = {"trend", "comparison", "distribution", "correlation", "anomaly"}
            allowed_sections = {
                "operating_goal": "operating_goal",
                "key_metrics": "key_metrics",
                "execution_path": "execution_path",
                "uncertainty": "uncertainty"
            }
            normalized = {}
            for section_key, section_value in data.items():
                if section_key not in allowed_sections:
                    continue
                if isinstance(section_value, dict):
                    insights = section_value.get("insights")
                else:
                    insights = section_value
                if not isinstance(insights, list):
                    continue
                cleaned = []
                for item in insights:
                    if not isinstance(item, dict):
                        continue
                    insight_type = item.get("insight_type")
                    if insight_type not in allowed_types:
                        insight_type = "comparison"
                    description = str(item.get("description") or "").strip()
                    key_findings = item.get("key_findings") or []
                    if not isinstance(key_findings, list):
                        key_findings = [str(key_findings)]
                    key_findings = [str(k).strip() for k in key_findings if str(k).strip()]
                    related_items = item.get("related_items") or []
                    if not isinstance(related_items, list):
                        related_items = [str(related_items)]
                    related_items = [str(k).strip() for k in related_items if str(k).strip()]
                    if not related_items:
                        continue
                    if not description and not key_findings:
                        continue
                    cleaned.append({
                        "insight_type": insight_type,
                        "description": description or (key_findings[0] if key_findings else ""),
                        "key_findings": key_findings,
                        "related_items": related_items
                    })
                if cleaned:
                    normalized[section_key] = {"insights": cleaned}
            return normalized

        # Step 1: 抽取可视化数据清单（只输出JSON）
        data_extraction_prompt = f"""
你是金融分析数据抽取助手。请从给定文本中抽取可视化需要的数据清单。
只输出JSON，不要输出任何解释或代码块。

数据来源（年报原文节选）：
{str(guidance_data)}

补充的关键指标线索：
{str(key_metrics_data)}

输出JSON结构（必须严格遵守）：
{{
  "datasets": [
    {{
      "topic": "核心指标锚点/经营目标方向/关键执行路径",
      "metric": "指标名称",
      "values": [
        {{"period": "年份/期间", "value": "数值", "unit": "单位", "direction": "up/down/flat", "change": "同比/环比"}}
      ],
      "source": "来源描述"
    }}
  ],
  "risks": [
    {{"risk": "风险名称", "impact": "影响对象", "probability": "高/中/低", "source": "来源描述"}}
  ],
  "execution_path": [
    {{"action": "执行动作", "evidence": "指标或变化证据"}}
  ]
}}

约束：
- 只能使用给定文本中的可核验数据
- 若缺失就填空数组，不要编造
"""

        extracted_data = {}
        try:
            data_response = await llm.achat([
                ChatMessage(role="system", content="你是金融数据抽取助手，只输出JSON。"),
                ChatMessage(role="user", content=data_extraction_prompt)
            ])
            data_text = data_response.message.content if hasattr(data_response, "message") else str(data_response)
            extracted_data = _extract_json_block(data_text)
        except Exception as data_error:
            logger.warning(f"⚠️ [generate_business_guidance] 数据抽取失败: {data_error}")
            extracted_data = {}

        # Step 2: 基于数据清单生成可视化指令（只输出JSON）
        visualization_prompt = f"""
你是可视化生成助手。请基于结构化数据清单生成可视化指令。
只输出JSON，不要输出任何解释或代码块。

结构化数据清单：
{extracted_data}

输出JSON结构（必须严格遵守）：
{{
  "operating_goal": {{
    "chart_type": "status_card",
    "stage": "经营阶段/基调",
    "priority": ["风险控制", "盈利稳定", "规模增长"]
  }},
  "key_metrics": {{
    "chart_type": "status_bar",
    "items": [
      {{"name": "指标名", "value": "数值", "trend": "up/down/flat", "note": "解读"}}
    ]
  }},
  "execution_path": {{
    "chart_type": "structure_change",
    "items": [
      {{"action": "执行动作", "evidence": "指标证据"}}
    ]
  }},
  "uncertainty": {{
    "chart_type": "risk_matrix",
    "items": [
      {{"risk": "风险", "impact": "影响对象", "probability": "高/中/低"}}
    ]
  }}
}}

约束：
- 如果数据不足，对应items为空数组
- 只使用提供的结构化数据，不得新增数据
"""

        visualization_spec = {}
        try:
            viz_response = await llm.achat([
                ChatMessage(role="system", content="你是可视化生成助手，只输出JSON。"),
                ChatMessage(role="user", content=visualization_prompt)
            ])
            viz_text = viz_response.message.content if hasattr(viz_response, "message") else str(viz_response)
            visualization_spec = _extract_json_block(viz_text)
        except Exception as viz_error:
            logger.warning(f"⚠️ [generate_business_guidance] 可视化指令生成失败: {viz_error}")
            visualization_spec = {}

        # Step 3: 基于可视化指令生成洞察（只输出JSON）
        insights_prompt = f"""
你是可视化洞察生成助手。请基于可视化指令与结构化数据清单生成洞察。
只输出JSON，不要输出任何解释或代码块。

可视化指令：
{visualization_spec}

结构化数据清单：
{extracted_data}

输出JSON结构（必须严格遵守）：
{{
  "operating_goal": {{
    "insights": [
      {{"insight_type": "comparison", "description": "洞察描述", "key_findings": ["要点1", "要点2"], "related_items": ["经营阶段/基调"]}}
    ]
  }},
  "key_metrics": {{
    "insights": [
      {{"insight_type": "trend", "description": "洞察描述", "key_findings": ["要点1", "要点2"], "related_items": ["指标名1", "指标名2"]}}
    ]
  }},
  "execution_path": {{
    "insights": [
      {{"insight_type": "comparison", "description": "洞察描述", "key_findings": ["要点1", "要点2"], "related_items": ["执行动作1", "执行动作2"]}}
    ]
  }},
  "uncertainty": {{
    "insights": [
      {{"insight_type": "anomaly", "description": "洞察描述", "key_findings": ["要点1", "要点2"], "related_items": ["风险1", "风险2"]}}
    ]
  }}
}}

约束：
- 每个板块最多2条洞察
- 若无数据，对应insights为空数组
- 只使用给定数据，不得编造
- insight_type 只能是: trend, comparison, distribution, correlation, anomaly
- related_items 必须从对应视图的条目中选取，且至少1个
- key_metrics 的 related_items 只能来自 key_metrics.items[].name
- execution_path 的 related_items 只能来自 execution_path.items[].action
- uncertainty 的 related_items 只能来自 uncertainty.items[].risk
- operating_goal 的 related_items 固定为 ["经营阶段/基调"]
"""

        visualization_insights = {}
        try:
            insights_response = await llm.achat([
                ChatMessage(role="system", content="你是可视化洞察生成助手，只输出JSON。"),
                ChatMessage(role="user", content=insights_prompt)
            ])
            insights_text = insights_response.message.content if hasattr(insights_response, "message") else str(insights_response)
            visualization_insights = _extract_json_block(insights_text)
            visualization_insights = _normalize_visualization_insights(visualization_insights)
        except Exception as insight_error:
            logger.warning(f"⚠️ [generate_business_guidance] 可视化洞察生成失败: {insight_error}")
            visualization_insights = {}

        prompt = f"""
你是一名专业的金融分析师，负责在智能财务分析系统中生成业绩指引洞察。

你的任务是：
- 基于年报中可核验的数据与文本
- 压缩管理层已披露的经营判断与业绩指引含义
- 输出结论型洞察（不含可视化指令）

重要说明：
- 你不是在预测未来
- 你不是在复述年报
- 你是在把管理层判断压缩为可决策信息

## 数据来源
以下数据来自{company_name} {year}年度年报中的业绩指引与经营计划部分：

{str(guidance_data)}

补充的关键指标线索（如有）：
{str(key_metrics_data)}

## 任务说明
请基于年报内容，围绕以下四个固定板块生成结果：
1. 经营目标方向
2. 核心指标锚点
3. 关键执行路径
4. 不确定性与边界

## 输出要求（必须严格遵守）
- 洞察面向用户阅读，只包含判断与结论，不复述原文
- 洞察必须显式引用具体数值
- 经营目标方向必须包含≥3个具体数值，并明确公司处于进攻/防守/转型中的哪一类
- 核心指标锚点必须包含≥3个指标数据（含数值与口径/同比）
- 不确定性与边界必须引用≥2个风险相关指标
- 不得输出任何示例表格或分析过程
- 若无法形成可靠结论，必须明确输出：数据不足，无法生成洞察
- 只使用给定数据与结构化数据清单，不得新增或编造数值

## 结构化数据清单（供参考）
{extracted_data}

## 字段清单（用于组织与结构化输出，不是最终展示）
以下结构仅用于组织内容，**不要输出JSON或代码块**：
{{
  "guidance_period": "业绩预告期间，如'2025年度'",
  "expected_performance": "经营目标方向的洞察（1段结论型文字）",
  "parent_net_profit_range": "归母净利润范围（如有，否则null）",
  "parent_net_profit_growth_range": "归母净利润增长率范围（如有，否则null）",
  "non_recurring_profit_range": "扣非净利润范围（如有，否则null）",
  "eps_range": "基本每股收益范围（如有，否则null）",
  "revenue_range": "营业收入范围（如有，否则null）",
  "key_metrics": ["核心指标锚点洞察（含数值/口径/同比）"],
  "business_specific_guidance": ["关键执行路径洞察（结构变化/资源倾斜/风控动作）"],
  "risk_warnings": ["不确定性与边界洞察（风险+指标变化）"]
}}

### 重要提示：
- 如果某些数据缺失，请如实说明，不要编造
- “核心指标锚点”必须有具体数值支撑，优先从“补充的关键指标线索”中提炼
"""

        # 使用结构化输出 - 添加异常处理和性能监控
        response = None
        import time
        structured_llm_start = time.time()
        try:
            sllm = llm.as_structured_llm(BusinessGuidance)
            raw_response = await sllm.achat([
                ChatMessage(role="system", content="你是一个专业的财务分析师,擅长分析业绩指引。请按字段提供清晰内容，系统会自动结构化，不要输出JSON或代码块。"),
                ChatMessage(role="user", content=prompt)
            ])
            
            # 检查响应类型 - 处理字符串响应
            if isinstance(raw_response, str):
                logger.warning(f"⚠️ [generate_business_guidance] 结构化LLM返回字符串，尝试解析JSON")
                import json
                import re
                json_match = re.search(r'\{[\s\S]*\}', raw_response)
                if json_match:
                    parsed_data = json.loads(json_match.group(0))
                    if 'business_guidance' in parsed_data:
                        parsed_data = parsed_data['business_guidance']
                    response = BusinessGuidance(**parsed_data) if isinstance(parsed_data, dict) and 'guidance_period' in parsed_data else parsed_data
                else:
                    response = BusinessGuidance(
                        guidance_period=f"{year}年度",
                        expected_performance=raw_response
                    )
            elif isinstance(raw_response, BusinessGuidance):
                response = raw_response
            elif hasattr(raw_response, 'message') and hasattr(raw_response.message, 'content'):
                # 处理Response对象，message.content可能是字符串
                content = raw_response.message.content
                if isinstance(content, str):
                    logger.warning(f"⚠️ [generate_business_guidance] 响应message.content是字符串，尝试解析JSON")
                    import json
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', content)
                    if json_match:
                        parsed_data = json.loads(json_match.group(0))
                        if 'business_guidance' in parsed_data:
                            parsed_data = parsed_data['business_guidance']
                        response = BusinessGuidance(**parsed_data) if isinstance(parsed_data, dict) and 'guidance_period' in parsed_data else parsed_data
                    else:
                        response = BusinessGuidance(
                            guidance_period=f"{year}年度",
                            expected_performance=content
                        )
                else:
                    response = content
            else:
                response = raw_response
            
            structured_llm_time = time.time() - structured_llm_start
            logger.info(f"✅ [generate_business_guidance] 结构化输出成功，耗时: {structured_llm_time:.2f}秒")
        except (AttributeError, ValueError, TypeError) as structured_error:
            error_type = type(structured_error).__name__
            error_msg = str(structured_error)
            structured_llm_time = time.time() - structured_llm_start
            
            # 更详细的错误信息
            if "model_dump_json" in error_msg or "AttributeError" in error_type:
                logger.warning(f"⚠️ [generate_business_guidance] 结构化LLM返回了字符串而非Pydantic模型（耗时: {structured_llm_time:.2f}秒）")
                logger.warning(f"[generate_business_guidance] 错误类型: {error_type}, 错误信息: {error_msg}")
                logger.info(f"[generate_business_guidance] 这是LlamaIndex的已知问题，将尝试从字符串解析JSON")
            else:
                logger.warning(f"⚠️ [generate_business_guidance] 结构化输出失败（{error_type}，耗时: {structured_llm_time:.2f}秒）: {error_msg}")
            
            logger.info(f"[generate_business_guidance] 尝试使用普通LLM输出并手动解析JSON")
            # 回退到普通LLM输出
            try:
                normal_response = await llm.achat([
                    ChatMessage(role="system", content="你是一个专业的财务分析师,擅长分析业绩指引。请按字段提供清晰内容，系统会自动结构化，不要输出JSON或代码块。"),
                    ChatMessage(role="user", content=prompt)
                ])
                
                # 提取并解析JSON
                if hasattr(normal_response, 'message'):
                    content = normal_response.message.content if hasattr(normal_response.message, 'content') else str(normal_response.message)
                else:
                    content = str(normal_response)
                
                import json
                import re
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    json_str = json_match.group(0)
                    parsed_data = json.loads(json_str)
                    
                    # 处理嵌套结构
                    if 'business_guidance' in parsed_data:
                        parsed_data = parsed_data['business_guidance']
                    elif len(parsed_data) == 1 and not any(k in parsed_data for k in ['guidance_period', 'expected_performance']):
                        parsed_data = list(parsed_data.values())[0]
                    
                    try:
                        response = BusinessGuidance(**parsed_data)
                        logger.info(f"✅ 手动解析JSON成功")
                    except Exception as validation_error:
                        logger.warning(f"⚠️ JSON验证失败，返回部分数据: {str(validation_error)}")
                        # 返回部分数据，至少包含基本信息
                        response = parsed_data if isinstance(parsed_data, dict) else {"content": content}
                else:
                    response = BusinessGuidance(
                        guidance_period=f"{year}年度",
                        expected_performance=content
                    )
            except Exception as fallback_error:
                logger.error(f"❌ 回退方案也失败: {str(fallback_error)}")
                # 返回错误信息，但不中断流程
                response = {
                    "error": f"生成失败: {str(fallback_error)}",
                    "content": content if 'content' in locals() else str(fallback_error)
                }

        logger.info(f"✅ 业绩指引生成成功")
        
        # 处理响应 - 确保返回字典格式
        result_dict = None
        
        # 如果response是字典且包含error，直接返回
        if isinstance(response, dict) and 'error' in response:
            result_dict = response
        # 首先检查是否是Pydantic模型
        elif isinstance(response, BusinessGuidance):
            result_dict = response.model_dump()
        elif hasattr(response, 'raw'):
            raw_data = response.raw
            if hasattr(raw_data, 'model_dump'):
                try:
                    result_dict = raw_data.model_dump()
                except Exception as e:
                    logger.warning(f"model_dump() 失败: {e}")
            elif isinstance(raw_data, dict):
                result_dict = raw_data
            elif isinstance(raw_data, str):
                import json
                try:
                    result_dict = json.loads(raw_data)
                except json.JSONDecodeError:
                    result_dict = {"content": raw_data}
            else:
                result_dict = {"content": str(raw_data)}
        
        if result_dict is None:
            if hasattr(response, 'model_dump'):
                try:
                    result_dict = response.model_dump()
                except Exception:
                    pass
            elif isinstance(response, dict):
                result_dict = response
            else:
                result_dict = {"content": str(response)}
        
        if not isinstance(result_dict, dict):
            result_dict = {"content": str(result_dict)}
        
        result_dict["company_name"] = company_name
        result_dict["year"] = year
        if visualization_spec:
            result_dict["visualization_spec"] = visualization_spec
        if visualization_insights:
            result_dict["visualization_insights"] = visualization_insights
        
        # 数据验证和清理
        result_dict = _validate_and_clean_data(result_dict, BusinessGuidance)
        
        return result_dict
        
    except Exception as e:
        logger.error(f"❌ 生成业绩指引失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "error": f"生成业绩指引失败: {str(e)}",
            "company_name": company_name,
            "year": year
        }


async def generate_business_highlights(
    company_name: Annotated[str, "公司名称"],
    year: Annotated[str, "年份"],
    query_engine: Any
) -> Dict[str, Any]:
    """
    生成业务亮点章节
    
    包括各业务板块的亮点和成就
    
    Args:
        company_name: 公司名称
        year: 年份
        query_engine: 查询引擎
    
    Returns:
        业务亮点的结构化数据
    """
    try:
        logger.info(f"开始生成业务亮点: {company_name} {year}年")
        
        # 检索业务亮点数据
        query = f"{company_name} {year}年 业务亮点 主要成就 重大项目 技术创新 市场拓展"
        highlights_data = query_engine.query(query)
        
        # 使用 LLM 生成结构化的业务亮点
        llm = Settings.llm

        prompt = f"""
作为资深业务分析师，请基于以下数据，生成{company_name} {year}年度的专业业务亮点分析。

## 数据来源
以下数据来自{company_name} {year}年度年报中的业务亮点、主要成就、重大项目等部分：

{str(highlights_data)}

## 分析要求
请生成结构化的业务亮点分析，要求如下：

### 1. 各业务类型的亮点描述
- 按业务板块分类总结亮点（如主营业务、新业务、创新业务等）
- 每个业务板块列出3-5个核心亮点
- 突出各业务的创新点、突破点和竞争优势
- 用具体数据和事实支撑亮点描述

### 2. 主要成就列表
- 识别年度最重要的成就和里程碑
- 包括市场拓展、技术创新、战略合作等
- 说明成就对公司发展的意义
- 按重要性排序，突出核心成就

### 3. 业务亮点总结
- 综合各业务亮点，提炼核心主题
- 识别公司整体业务发展的主旋律
- 评估业务亮点对公司未来发展的影响
- 提供前瞻性的业务展望

## ⚠️ 严格输出要求（必须遵守）
你必须输出一个有效的JSON对象，且仅输出JSON，不要有任何其他文字说明。

### JSON格式要求：
1. 必须是有效的JSON格式，可以直接被JSON.parse()解析
2. 不要使用markdown代码块（不要用```json包裹）
3. 不要有任何前缀或后缀文字
4. 直接输出JSON对象，从{{开始，以}}结束
5. 所有字符串值必须用双引号包裹
6. 所有数字和布尔值不要用引号
7. 确保所有必需字段都存在

### JSON结构（必须严格遵循）：
{{
  "highlights": [
    {{
      "business_type": "业务类型名称",
      "highlights": "业务亮点详细描述",
      "achievements": ["成就1", "成就2", ...]
    }},
    ...
  ],
  "overall_summary": "业务亮点总结文字"
}}

### 重要提示：
- highlights数组至少包含一个元素
- 所有字段都必须存在，不能省略
- 直接输出上述JSON结构，不要有任何其他内容
"""

        # 使用结构化输出 - 添加异常处理和性能监控
        response = None
        import time
        structured_llm_start = time.time()
        try:
            sllm = llm.as_structured_llm(BusinessHighlights)
            raw_response = await sllm.achat([
                ChatMessage(role="system", content="你是一个专业的业务分析师,擅长总结业务亮点。你必须严格按照用户要求的JSON格式输出，只输出JSON，不要有任何其他文字。"),
                ChatMessage(role="user", content=prompt)
            ])
            
            # 检查响应类型 - 处理字符串响应
            if isinstance(raw_response, str):
                logger.warning(f"⚠️ [generate_business_highlights] 结构化LLM返回字符串，尝试解析JSON")
                import json
                import re
                json_match = re.search(r'\{[\s\S]*\}', raw_response)
                if json_match:
                    parsed_data = json.loads(json_match.group(0))
                    if 'business_highlights' in parsed_data:
                        parsed_data = parsed_data['business_highlights']
                    response = BusinessHighlights(**parsed_data) if isinstance(parsed_data, dict) and 'business_types' in parsed_data else parsed_data
                else:
                    raise ValueError("无法从字符串响应提取JSON")
            elif isinstance(raw_response, BusinessHighlights):
                response = raw_response
            elif hasattr(raw_response, 'message') and hasattr(raw_response.message, 'content'):
                # 处理Response对象，message.content可能是字符串
                content = raw_response.message.content
                if isinstance(content, str):
                    logger.warning(f"⚠️ [generate_business_highlights] 响应message.content是字符串，尝试解析JSON")
                    import json
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', content)
                    if json_match:
                        parsed_data = json.loads(json_match.group(0))
                        if 'business_highlights' in parsed_data:
                            parsed_data = parsed_data['business_highlights']
                        response = BusinessHighlights(**parsed_data) if isinstance(parsed_data, dict) and 'business_types' in parsed_data else parsed_data
                    else:
                        raise ValueError("无法从message.content提取JSON")
                else:
                    response = content
            else:
                response = raw_response
            
            structured_llm_time = time.time() - structured_llm_start
            logger.info(f"✅ [generate_business_highlights] 结构化输出成功，耗时: {structured_llm_time:.2f}秒")
        except (AttributeError, ValueError, TypeError) as structured_error:
            error_type = type(structured_error).__name__
            error_msg = str(structured_error)
            structured_llm_time = time.time() - structured_llm_start
            
            # 更详细的错误信息
            if "model_dump_json" in error_msg or "AttributeError" in error_type:
                logger.warning(f"⚠️ [generate_business_highlights] 结构化LLM返回了字符串而非Pydantic模型（耗时: {structured_llm_time:.2f}秒）")
                logger.warning(f"[generate_business_highlights] 错误类型: {error_type}, 错误信息: {error_msg}")
                logger.info(f"[generate_business_highlights] 这是LlamaIndex的已知问题，将尝试从字符串解析JSON")
            else:
                logger.warning(f"⚠️ [generate_business_highlights] 结构化输出失败（{error_type}，耗时: {structured_llm_time:.2f}秒）: {error_msg}")
            
            logger.info(f"[generate_business_highlights] 尝试使用普通LLM输出并手动解析JSON")
            # 回退到普通LLM输出
            try:
                normal_response = await llm.achat([
                    ChatMessage(role="system", content="你是一个专业的业务分析师,擅长总结业务亮点。你必须严格按照用户要求的JSON格式输出，只输出JSON，不要有任何其他文字。"),
                    ChatMessage(role="user", content=prompt)
                ])
                
                # 提取并解析JSON
                if hasattr(normal_response, 'message'):
                    content = normal_response.message.content if hasattr(normal_response.message, 'content') else str(normal_response.message)
                else:
                    content = str(normal_response)
                
                import json
                import re
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    json_str = json_match.group(0)
                    parsed_data = json.loads(json_str)
                    
                    # 处理嵌套结构
                    if 'business_highlights' in parsed_data:
                        parsed_data = parsed_data['business_highlights']
                    elif len(parsed_data) == 1:
                        parsed_data = list(parsed_data.values())[0]
                    
                    try:
                        response = BusinessHighlights(**parsed_data)
                        logger.info(f"✅ 手动解析JSON成功")
                    except Exception as validation_error:
                        logger.warning(f"⚠️ JSON验证失败，返回部分数据: {str(validation_error)}")
                        response = parsed_data if isinstance(parsed_data, dict) else {"content": content}
                else:
                    raise ValueError("无法从响应中提取JSON")
            except Exception as fallback_error:
                logger.error(f"❌ 回退方案也失败: {str(fallback_error)}")
                response = {
                    "error": f"生成失败: {str(fallback_error)}",
                    "content": content if 'content' in locals() else str(fallback_error)
                }

        logger.info(f"✅ 业务亮点生成成功")
        
        # 处理响应 - 确保返回字典格式
        result_dict = None
        
        # 如果response是字典且包含error，直接返回
        if isinstance(response, dict) and 'error' in response:
            result_dict = response
        # 首先检查是否是Pydantic模型
        elif isinstance(response, BusinessHighlights):
            result_dict = response.model_dump()
        elif hasattr(response, 'raw'):
            raw_data = response.raw
            if hasattr(raw_data, 'model_dump'):
                try:
                    result_dict = raw_data.model_dump()
                except Exception as e:
                    logger.warning(f"model_dump() 失败: {e}")
            elif isinstance(raw_data, dict):
                result_dict = raw_data
            elif isinstance(raw_data, str):
                import json
                try:
                    result_dict = json.loads(raw_data)
                except json.JSONDecodeError:
                    result_dict = {"content": raw_data}
            else:
                result_dict = {"content": str(raw_data)}
        
        if result_dict is None:
            if hasattr(response, 'model_dump'):
                try:
                    result_dict = response.model_dump()
                except Exception:
                    pass
            elif isinstance(response, dict):
                result_dict = response
            else:
                result_dict = {"content": str(response)}
        
        if not isinstance(result_dict, dict):
            result_dict = {"content": str(result_dict)}
        
        result_dict["company_name"] = company_name
        result_dict["year"] = year
        
        # 数据验证和清理
        result_dict = _validate_and_clean_data(result_dict, BusinessHighlights)
        
        return result_dict
        
    except Exception as e:
        logger.error(f"❌ 生成业务亮点失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "error": f"生成业务亮点失败: {str(e)}",
            "company_name": company_name,
            "year": year
        }


async def _llm_correlation_analysis(
    indicator_extraction: List[Dict[str, Any]],
    variable_table: List[Dict[str, Any]],
    year: str,
    llm: Any
) -> tuple:
    """使用 LLM 生成相关性分析结果，返回 (correlation_results, data_sufficiency)。"""
    import json
    import re
    prompt = f"""
你是一位专业投资分析师。请严格按以下步骤执行并输出。

## 目标
从输入变量表中提取核心财务指标的时间序列，计算 Pearson 相关系数矩阵，并输出矩阵（列表形式）。

## 核心财务指标（8 项）
净息差、ROE、ROA、不良率、拨备覆盖率、成本收入比、信贷成本、资本充足率。

## 输入

### 指标抽取
{json.dumps(indicator_extraction or [], ensure_ascii=False, indent=2)}

### 输入变量表（同一 metric 多行 = 多期数据，period 为年份）
{json.dumps(variable_table or [], ensure_ascii=False, indent=2)}

## 步骤 1：从 variable_table 构建时间序列
- 按 metric 分组，收集每项指标的 (period, value) 列表。
- 数据标准化：统一单位与命名（如 ROE、净资产收益率 视为同一指标）。

## 步骤 2：计算 Pearson 相关系数矩阵
- 对上述 8 项指标**两两**判断：若两者在 variable_table 中存在**至少 3 个共同 period**，则计算该两列数值的 Pearson 相关系数，并输出一条记录（target_metric, driver_metric, correlation, significance, interpretation, data_points）。
- **必须尽可能输出**：只要有一对指标具备至少 3 个共同时间点，correlation_results 就不得为空。多对满足条件则全部输出。
- 显著性解读：|r|>0.7 强相关，0.5~0.7 中强相关，0.3~0.5 弱相关，<0.3 无显著相关；并区分正/负。

## 步骤 3：数据充分性
- 若至少有一对指标有 3 个及以上共同时间点并已输出，则 is_sufficient 为 true，sample_description 写明时间范围（如"2022-2024年3期"）。
- 若 variable_table 中没有任何一对指标具备 3 个共同 period，则 correlation_results 可为 []，is_sufficient 为 false，reason 说明"共同时间点不足三年"。

请**只输出一个 JSON 对象**，无其他文字。格式如下：
{{
  "correlation_results": [
    {{
      "target_metric": "指标A名称",
      "driver_metric": "指标B名称",
      "correlation": 0.85,
      "significance": "强正相关",
      "interpretation": "简要业务解读",
      "data_points": 5
    }}
  ],
  "data_sufficiency": {{
    "is_sufficient": true,
    "reason": null,
    "sample_description": "如：2022-2024年3期"
  }}
}}
"""
    try:
        response = await llm.achat([
            ChatMessage(role="system", content="你是专业投资分析师，擅长相关性分析。必须只输出一个合法 JSON 对象，无其他内容。"),
            ChatMessage(role="user", content=prompt)
        ])
        content = response.message.content if hasattr(response, "message") and hasattr(response.message, "content") else str(response)
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return [], {"is_sufficient": False, "reason": "LLM 未返回有效 JSON", "sample_description": None}
        parsed = json.loads(match.group(0))
        results = parsed.get("correlation_results") or []
        sufficiency = parsed.get("data_sufficiency") or {}
        sufficiency.setdefault("is_sufficient", bool(results))
        return results, sufficiency
    except Exception as e:
        logger.warning(f"LLM 相关性分析失败: {e}")
        return [], {"is_sufficient": False, "reason": str(e), "sample_description": None}


async def _llm_factor_analysis(
    indicator_extraction: List[Dict[str, Any]],
    variable_table: List[Dict[str, Any]],
    year: str,
    llm: Any
) -> tuple:
    """使用 LLM 生成因子分析结果，返回 (factor_dict, data_sufficiency)。"""
    import json
    import re
    prompt = f"""
你是一位专业投资分析师，请基于以下指标与变量表，**严格按照下列四步**完成因子分析，并在最后输出系统要求的 JSON。

### 指标抽取（参考）
{json.dumps(indicator_extraction or [], ensure_ascii=False, indent=2)}

### 输入变量表（参考）
{json.dumps(variable_table or [], ensure_ascii=False, indent=2)}

============================
第一步：构建指标数据矩阵
============================
从年报中提取最近 3–5 年的核心财务指标（至少3年）。
指标选择遵循以下原则：
（1）盈利能力指标
ROE、ROA、净利润率/净息差（银行）、毛利率（制造业）
（2）风险指标
不良率（银行）/资产减值率、资产负债率、资本充足率（金融机构）、流动比率
（3）效率指标
成本收入比、周转率类指标、营业费用率、运营效率指标

构建如下格式数据表：年份 指标1 指标2...
要求：所有指标必须为数值型；处理缺失值；对指标进行标准化（Z-score）。

============================
第二步：执行因子分析
============================
请执行标准因子分析流程：
计算相关系数矩阵 → 提取特征值（Eigenvalues）→ 根据特征值>1原则确定因子数量 → 计算因子载荷矩阵 → 计算共同度 → 计算方差贡献率与累计贡献率 → 进行因子旋转（如Varimax）。

输出：
（1）因子载荷矩阵
格式：| 指标 | 因子1 | 因子2 | 因子3 | 共同度 |
并根据载荷大小识别：每个因子的“核心解释变量”、因子经济含义命名（例如：因子1=盈利因子，因子2=风险因子，因子3=效率因子）。

（2）方差贡献分析
| 因子 | 特征值 | 方差贡献率 | 累计贡献率 |
要求：累计贡献率≥80%；对因子重要性排序。

【表格格式强制要求】所有数据表必须使用 Markdown 管道表格格式，且每行表格数据必须在一行内写完，禁止将同一行的多个单元格拆成多行。示例（方差贡献分析正确写法）：
| 因子 | 特征值 | 方差贡献率 | 累计贡献率 |
|------|--------|------------|------------|
| 因子1：盈利与风险因子 | 4.94 | 70.6% | 70.6% |
| 因子2：资本与成本因子 | 2.06 | 29.4% | 100.0% |
禁止使用制表符或“表头一行、数据每个单元格单独一行”的错位格式，否则前端无法正确渲染。

============================
第三步：计算年度因子得分
============================
计算各年因子得分（标准化），构建综合得分（加权平均）：
综合得分 = Σ(因子得分 × 方差贡献率权重)
输出表格格式（每行一行，管道表格）：
| 年份 | 因子1得分 | 因子2得分 | 因子3得分 | 综合得分 |
|------|----------|----------|----------|----------|
| 2022 | x.xx | x.xx | x.xx | x.xx |
| 2023 | ... | ... | ... | ... |

============================
第四步：生成因子洞察报告
============================
请基于因子分析结果输出结构化分析报告：
一、因子结构识别：共提取多少个因子；每个因子解释的经济含义；主要载荷变量。
二、企业经营驱动拆解：盈利/风险/效率驱动因素；哪个因子主导公司经营变化、哪个因子出现恶化。
三、年度变化趋势分析：因子得分趋势、综合得分变化、驱动结构是否发生变化。
四、风险提示：高载荷风险指标、因子恶化方向。
五、投资判断：偏盈利驱动/偏风险驱动/偏效率驱动；结构性改善还是周期性波动；投资建议倾向（进攻/防守/观望）。

============================
输出格式要求
============================
必须包含：数据表、因子载荷矩阵、方差贡献表、因子得分表、结构化洞察。
不得输出无法计算的数据。若样本年份不足3年，需提示因子稳定性不足。

---
请在上述分析之后，**单独输出一个 JSON 对象**（便于系统解析），结构如下，不得缺少：
{{
  "factor_analysis": {{
    "factors": ["因子1名称", "因子2名称"],
    "factor_loadings": {{
      "因子1名称": {{ "指标A": 载荷值, "指标B": 载荷值 }},
      "因子2名称": {{ "指标A": 载荷值, "指标B": 载荷值 }}
    }},
    "variance_explained": {{ "因子1名称": 比例, "因子2名称": 比例 }},
    "interpretation": "第四步洞察报告的精炼总结（含因子结构、驱动拆解、趋势、风险与投资判断要点）",
    "data_points": 样本年数
  }},
  "factor_data_sufficiency": {{
    "is_sufficient": true或false,
    "reason": null或不足原因,
    "sample_description": "如：5年样本"
  }}
}}
若指标或样本不足无法完成因子分析，则 factors 为空数组、factor_loadings 为空对象，interpretation 中说明原因。
"""
    try:
        response = await llm.achat([
            ChatMessage(role="system", content="你是专业投资分析师，擅长因子分析。请严格按四步完成：指标矩阵→因子分析→年度得分→洞察报告；最后必须输出一个合法 JSON 对象。"),
            ChatMessage(role="user", content=prompt)
        ])
        content = response.message.content if hasattr(response, "message") and hasattr(response.message, "content") else str(response)
        # 优先匹配包含 factor_analysis 的 JSON（长回复中可能在文末）
        all_matches = list(re.finditer(r"\{[\s\S]*\}", content))
        match = None
        for m in reversed(all_matches):
            raw = m.group(0)
            if "factor_analysis" in raw and "factor_data_sufficiency" in raw:
                raw_clean = re.sub(r"[\x00-\x1f]", " ", raw)
                try:
                    parsed = json.loads(raw_clean)
                    if isinstance(parsed.get("factor_analysis"), dict):
                        match = m
                        break
                except json.JSONDecodeError:
                    continue
        if not match:
            match = all_matches[-1] if all_matches else None
        if not match:
            return (
                {"factors": [], "factor_loadings": {}, "variance_explained": {}, "interpretation": "LLM 未返回有效 JSON"},
                {"is_sufficient": False, "reason": "LLM 未返回有效 JSON", "sample_description": None}
            )
        json_str = re.sub(r"[\x00-\x1f]", " ", match.group(0))
        parsed = json.loads(json_str)
        fa = parsed.get("factor_analysis") or {}
        suff = parsed.get("factor_data_sufficiency") or {}
        suff.setdefault("is_sufficient", bool(fa.get("factors")))
        # 保留 LLM 完整回复（含数据表、因子载荷表、方差贡献表、因子得分表、第四步完整洞察），供界面展示
        if isinstance(content, str) and content.strip():
            fa["full_report"] = content.strip()
        return fa, suff
    except Exception as e:
        logger.warning(f"LLM 因子分析失败: {e}")
        return (
            {"factors": [], "factor_loadings": {}, "variance_explained": {}, "interpretation": str(e)},
            {"is_sufficient": False, "reason": str(e), "sample_description": None}
        )


async def generate_profit_forecast_and_valuation(
    company_name: Annotated[str, "公司名称"],
    year: Annotated[str, "年份"],
    query_engine: Any,
    model_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    生成投资策略章节（包含四个分析：相关性分析、多元线性回归、聚类分析、因子分析）
    
    包括:
    1. 指标自动识别与抽取
    2. 输入变量表构建
    3. 相关性分析
    4. 多元线性回归分析
    5. 因子分析
    6. 聚类分析
    7. 综合投资策略结论
    
    Args:
        company_name: 公司名称
        year: 年份
        query_engine: 查询引擎
        model_type: 模型类型，默认为"all"（执行所有分析）
    
    Returns:
        投资策略（包含四个分析）的结构化数据
    """
    try:
        _mt = (model_type or "").lower()
        if _mt == "clustering":
            logger.info(f"仅生成聚类分析: {company_name} {year}年")
        elif _mt == "factor_only":
            logger.info(f"仅生成因子分析: {company_name} {year}年")
        elif _mt == "correlation_only":
            logger.info(f"仅生成相关性分析: {company_name} {year}年")
        elif _mt == "earnings_forecast":
            logger.info(f"仅生成盈利预测: {company_name} {year}年")
        elif _mt == "valuation_anchor":
            logger.info(f"仅生成估值锚点分析: {company_name} {year}年")
        elif _mt == "comprehensive_strategy":
            logger.info(f"仅生成综合投资策略分析: {company_name} {year}年")
        else:
            logger.info(f"开始生成投资策略（相关性分析、聚类分析、因子分析）: {company_name} {year}年")
        
        # 先检索表格，再检索年报文本（同一份年报）
        table_query = (
            f"{company_name} {year}年 关键指标 表格 主要指标 表 "
            "股息率 分红率 市净率 PB ROE 净息差 NIM 非息收入 "
            "不良贷款率 核心一级资本充足率 拨备覆盖率 "
            "零售贷款增速 对公新兴行业贷款增速 房地产敞口不良率 风险加权资产"
        )
        report_query = (
            f"{company_name} {year}年 年报 管理层讨论与分析 财务指标 经营分析 "
            "股息率 分红率 市净率 PB ROE 净息差 NIM 非息收入增速 "
            "不良贷款率 核心一级资本充足率 拨备覆盖率 "
            "零售贷款增速 对公新兴行业贷款增速 房地产敞口不良率"
        )
        # 相关性分析专用：检索近三年核心财务指标（净息差、ROE、ROA、不良率、拨备覆盖率、成本收入比、信贷成本、资本充足率）
        correlation_query = (
            f"{company_name} 年报 近三年 历年 净息差 ROE ROA 不良率 拨备覆盖率 "
            "成本收入比 信贷成本 资本充足率 主要指标 表 财务数据"
        )
        table_data = query_engine.query(table_query)
        report_data = query_engine.query(report_query)
        correlation_data = query_engine.query(correlation_query)
        forecast_data = f"【表格】\n{str(table_data)}\n\n【年报文本】\n{str(report_data)}\n\n【相关性分析用-近三年核心指标】\n{str(correlation_data)}"
        
        # 使用 LLM 生成结构化的投资策略
        llm = Settings.llm
        # 支持: all, correlation, clustering, correlation_only, factor_only, earnings_forecast, valuation_anchor, comprehensive_strategy（已去掉 regression_only）
        normalized_model = (model_type or "all").lower()
        if normalized_model not in {"correlation", "clustering", "all", "correlation_only", "factor_only", "earnings_forecast", "valuation_anchor", "comprehensive_strategy"}:
            normalized_model = "all"

        # 综合投资策略分析：基于盈利预测 + 估值锚点结论，输出SWOT/打分/上下行/策略/跟踪指标
        if normalized_model == "comprehensive_strategy":
            # 先尝试复用缓存，缺失时再补算，避免重复点击时重复执行耗时步骤
            earnings_report = _get_cached_strategy_report(
                company_name=company_name,
                year=year,
                report_type="earnings_forecast_report"
            ) or ""
            valuation_report = _get_cached_strategy_report(
                company_name=company_name,
                year=year,
                report_type="valuation_anchor_report"
            ) or ""

            if earnings_report:
                logger.info("✅ [strategy_cache] 命中盈利预测缓存: %s %s", company_name, year)
            else:
                logger.info("ℹ️ [strategy_cache] 盈利预测缓存未命中，开始补算: %s %s", company_name, year)
                earnings_output = await generate_profit_forecast_and_valuation(
                    company_name=company_name,
                    year=year,
                    query_engine=query_engine,
                    model_type="earnings_forecast"
                )
                if isinstance(earnings_output, dict):
                    earnings_report = str(earnings_output.get("earnings_forecast_report") or "")
                if earnings_report.strip():
                    _set_cached_strategy_report(
                        company_name=company_name,
                        year=year,
                        report_type="earnings_forecast_report",
                        content=earnings_report
                    )

            if valuation_report:
                logger.info("✅ [strategy_cache] 命中估值锚点缓存: %s %s", company_name, year)
            else:
                logger.info("ℹ️ [strategy_cache] 估值锚点缓存未命中，开始补算: %s %s", company_name, year)
                valuation_output = await generate_profit_forecast_and_valuation(
                    company_name=company_name,
                    year=year,
                    query_engine=query_engine,
                    model_type="valuation_anchor"
                )
                if isinstance(valuation_output, dict):
                    valuation_report = str(valuation_output.get("valuation_anchor_report") or "")
                if valuation_report.strip():
                    _set_cached_strategy_report(
                        company_name=company_name,
                        year=year,
                        report_type="valuation_anchor_report",
                        content=valuation_report
                    )

            comprehensive_prompt = f"""
基于Prompt 1的盈利预测和Prompt 2的估值分析，
请完成以下综合投资策略的推导。

【公司名称】{company_name}
【报告年份】{year}

可用原始年报数据：
【年报表格数据】
{str(table_data)}

【年报正文数据】
{str(report_data)}

Prompt 1（盈利预测）输出：
{earnings_report}

Prompt 2（估值分析）输出：
{valuation_report}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第一步：SWOT分析（数据驱动，非空泛描述）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

对该公司做SWOT分析，要求：
- 每一条S/W/O/T都必须附带具体数据或年报引用（页码）
- 不接受没有数据支撑的泛泛描述
- 每个象限2-4条，共8-16条

| 优势(S) | 数据支撑 |
|---------|----------|
| 1. ？ | 具体数字+页码 |
| 2. ？ | |

| 劣势(W) | 数据支撑 |
|---------|----------|
| 1. ？ | 具体数字+页码 |

| 机会(O) | 数据支撑 |
|---------|----------|
| 1. ？ | 具体数字+页码 |

| 威胁(T) | 数据支撑 |
|---------|----------|
| 1. ？ | 具体数字+页码 |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第二步：四维评估打分
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

对以下四个维度进行评估打分（1-5分），并说明理由：

| 维度 | 评分(1-5) | 权重 | 加权得分 | 评分依据 |
|------|-----------|------|----------|----------|
| 安全边际 | ？ | 30% | ？ | 来自Prompt 2估值结论：当前PB/PE vs 历史分位 |
| 盈利趋势 | ？ | 25% | ？ | 来自Prompt 1预测：营收/利润增速方向 |
| 催化因素 | ？ | 25% | ？ | SWOT中的O+S：是否有近期可兑现的积极因素 |
| 风险因素 | ？ | 20% | ？ | SWOT中的W+T：风险是否已被估值反映(风险低给高分) |
| **综合** | | **100%** | **？** | **>3.5偏积极 / 2.5-3.5中性 / <2.5偏谨慎** |

雷达图数据（必填）：在第二步表格之后，请紧接着输出一个雷达图专用数据块，便于前端绘制四维雷达图。格式要求：
- 使用代码块，标记为 ```radar_scores 或 ```json；
- 内容为 JSON 对象，包含键 radar_scores，其值为对象，内含 dimensions（四维名称数组）、scores（四个评分数组），顺序与上表一致；
- 四维顺序固定为：安全边际、盈利趋势、催化因素、风险因素；
- scores 中每个值为 1–5 的数值（与表格中的「评分(1-5)」一致）。

示例：
```json
{{"radar_scores": {{"dimensions": ["安全边际", "盈利趋势", "催化因素", "风险因素"], "scores": [4, 3, 3, 4]}}}}
```

打分标准：
- 5分：非常积极（如PB处于历史最低5%分位+盈利拐点确认）
- 4分：积极（如估值低位+盈利企稳）
- 3分：中性（如估值合理+盈利持平）
- 2分：谨慎（如估值偏高或盈利下行）
- 1分：非常谨慎（如估值泡沫+盈利恶化）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第三步：上行/下行空间量化
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

基于Prompt 2的估值结论，计算：
(a) 上行空间 = (中性目标价 - 当前股价) / 当前股价 = ？%
(b) 下行风险 = (极端悲观价 - 当前股价) / 当前股价 = ？%
(c) 风险收益比 = |上行空间| / |下行风险| = ？x
    → >2x为好交易, 1-2x一般, <1x不划算

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第四步：分类策略建议
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

请对三类投资者分别给出策略：

| 投资者类型 | 策略 | 建仓区间 | 目标价 | 止损价 | 核心逻辑 |
|------------|------|----------|--------|--------|----------|
| 价值型（看重安全边际+股息）| ？ | ？ | ？ | ？ | ？ |
| 成长型（看重盈利拐点+催化）| ？ | ？ | ？ | ？ | ？ |
| 配置型（板块均衡配置）| ？ | ？ | ？ | ？ | ？ |

建仓区间和目标价必须用Prompt 2的估值结果推导（如"PB=0.5x对应？元"）。
止损价必须有明确的估值或基本面触发条件。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第五步：关键跟踪指标
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

列出未来1-2个季度需要重点跟踪的3-5个指标，说明：
- 该指标当前值是多少（来自年报）
- 如果向好变化，意味着什么（加仓信号）
- 如果向差变化，意味着什么（减仓/止损信号）

| 跟踪指标 | 当前值 | 向好信号 | 向差信号 |
|----------|--------|----------|----------|
| ？ | ？ | ？ | ？ |

输出要求：
1. 使用 Markdown 完整输出，所有表格都使用标准 Markdown 管道格式。
2. 所有关键结论必须带具体数据和页码/来源，缺失时标“页码待核实/需补充”。
3. 结果要可执行，避免空泛描述。
4. 第二步四维评估打分后必须包含雷达图数据块（```radar_scores 或 ```json），用于生成「综合策略-四维评估打分」雷达图；维度顺序为：安全边际、盈利趋势、催化因素、风险因素，分值为 1–5。
"""

            comprehensive_raw = await llm.achat([
                ChatMessage(role="system", content="你是专业卖方投资策略分析师。请严格按五步输出，强调数据证据、页码与可执行性。"),
                ChatMessage(role="user", content=comprehensive_prompt)
            ])
            if hasattr(comprehensive_raw, "message") and hasattr(comprehensive_raw.message, "content"):
                comprehensive_report = comprehensive_raw.message.content or ""
            else:
                comprehensive_report = str(comprehensive_raw or "")
            if comprehensive_report.strip():
                _set_cached_strategy_report(
                    company_name=company_name,
                    year=year,
                    report_type="comprehensive_strategy_report",
                    content=comprehensive_report
                )

            return {
                "indicator_extraction": [],
                "variable_table": [],
                "correlation_results": [],
                "strategy_conclusion": {"short_term": "", "long_term": "", "risk_control": "", "key_signals": []},
                "data_sufficiency": {
                    "is_sufficient": False,
                    "reason": "综合策略模式不执行相关性/因子/聚类结构化分析",
                    "sample_description": None
                },
                "clustering_model": None,
                "notes": "综合投资策略分析模式执行完成",
                "earnings_forecast_report": earnings_report.strip(),
                "valuation_anchor_report": valuation_report.strip(),
                "comprehensive_strategy_report": comprehensive_report.strip(),
                "model_type": "comprehensive_strategy",
                "company_name": company_name,
                "year": year
            }

        # 估值锚点分析模式：基于年报与盈利预测上下文直接生成估值报告
        if normalized_model == "valuation_anchor":
            valuation_query = (
                f"{company_name} {year}年 年报 每股净资产 BV 总股本 归属净利润 DPS 股息 加权平均ROE "
                "归属股东权益 PB PE 估值 分红率 管理层讨论与分析"
            )
            valuation_data = query_engine.query(valuation_query)
            valuation_prompt = f"""
基于上一步的盈利预测结果和年报数据，请完成以下三种估值方法的分析。

【公司名称】{company_name}
【报告年份】{year}

你可以使用以下检索数据：
【年报表格数据】
{str(table_data)}

【年报正文数据】
{str(report_data)}

【补充估值相关数据】
{str(valuation_data)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第一步：提取估值所需基础数据
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

从年报中提取以下数据（标注页码）：

| 数据项 | 数值 | 年报页码 |
|--------|------|----------|
| 年末每股净资产(BV) | | |
| 总股本(股) | | |
| 归属净利润 | | |
| 年度每股股息(DPS) | | |
| 加权平均ROE | | |
| 年末归属股东权益 | | |

外部市场数据（需你自行搜索当前值）：
| 数据项 | 数值 | 来源 |
|--------|------|------|
| 当前股价 | | 需搜索 |
| 10年国债收益率 | | 需搜索 |
| 同行业可比公司平均PB | | 需搜索 |
| 同行业可比公司平均PE | | 需搜索 |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第二步：方法一——PB估值法（适合银行/重资产行业）
或 PE估值法（适合消费/科技等轻资产行业）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【PB法】适用：银行、保险、地产、公用事业等净资产可靠的行业
计算过程：
(a) 当前PB = 当前股价 / 每股净资产 = ？ / ？ = ？x
(b) 设定目标PB区间（基于可比公司和历史中枢）：
    - 悲观PB = ？x → 对应股价 = ？x × BV = ？元
    - 中性PB = ？x → 对应股价 = ？元
    - 乐观PB = ？x → 对应股价 = ？元
(c) 说明目标PB设定的依据（可比公司、历史分位数）

【PE法】适用：消费、科技、医药、制造等盈利驱动的行业
计算过程：
(a) 当前PE(TTM) = 当前股价 / 本年EPS = ？ / ？ = ？x
(b) 预测PE(Forward) = 当前股价 / 预测EPS(中性) = ？ / ？ = ？x
(c) 设定目标PE区间（基于可比公司和历史中枢）：
    - 悲观PE = ？x → 对应股价 = ？x × 预测EPS = ？元
    - 中性PE = ？x → 对应股价 = ？元
    - 乐观PE = ？x → 对应股价 = ？元
(d) 说明目标PE设定的依据

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第三步：方法二——股息率估值法（适合高分红公司）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

计算过程：
(a) 每股股息DPS = 年报披露值 = ？元
(b) 分红率 = DPS × 总股本 / 归属净利润 = ？%
(c) 当前股息率 = DPS / 当前股价 = ？%
(d) 与无风险利率对比：股息率 - 10年国债收益率 = ？% （风险溢价）
(e) 反推目标价：
    - 若股息率回归行业均值？% → 目标价 = DPS / ？% = ？元
    - 若维持当前股息率 → 价格 ≈ 当前股价

如果该公司不分红或分红率极低，跳过此方法，说明原因。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第四步：方法三——DDM/DCF简化估值
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【DDM戈登模型】适合：稳定分红的成熟公司（银行、公用事业）
(a) 可持续ROE假设 = ？%（来自Prompt 1的预测）
(b) 分红率 b = ？%
(c) 可持续增长率 g = ROE × (1-b) = ？%
(d) 要求回报率 r = ？%（通常8%-12%，说明取值依据）
(e) 理论PB = (ROE - g) / (r - g) = ？x
(f) 理论股价 = 理论PB × BV = ？元

检验：如果 r 接近 g，模型不稳定，需说明局限性。

【DCF简化版】适合：高成长公司（科技、医药、新能源）
(a) 预测未来3年自由现金流（基于Prompt 1的盈利预测 × 现金转化率）
(b) 第4年起假设永续增长率 g = ？%
(c) WACC = ？%
(d) 企业价值 = Σ FCF/(1+WACC)^t + 终值/(1+WACC)^n
(e) 股权价值 = 企业价值 - 净负债
(f) 每股价值 = 股权价值 / 总股本

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第五步：三种方法汇总
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| 估值方法 | 悲观/下限 | 中性 | 乐观/上限 | 当前股价 | 上行空间(中性) |
|----------|-----------|------|-----------|----------|----------------|
| PB/PE法 | ？元 | ？元 | ？元 | ？元 | ？% |
| 股息率法 | ？元 | ？元 | ？元 | ？元 | ？% |
| DDM/DCF | ？元 | ？元 | ？元 | ？元 | ？% |

基于三种方法的结果，给出综合合理估值区间。

输出要求：
1. 使用 Markdown 完整输出，保留所有公式“公式→代入→结果”。
2. 对所有关键数字标注来源（年报页码或外部来源）。
3. 若外部数据无法确认，明确标注“需手动补充/页码待核实”，不要编造。
4. 表格请使用标准 Markdown 管道格式，每个单元格保持单行。
"""

            valuation_raw = await llm.achat([
                ChatMessage(role="system", content="你是专业卖方分析师，擅长估值锚点分析。请严格按五步输出，并突出可追溯与可计算性。"),
                ChatMessage(role="user", content=valuation_prompt)
            ])
            if hasattr(valuation_raw, "message") and hasattr(valuation_raw.message, "content"):
                valuation_report = valuation_raw.message.content or ""
            else:
                valuation_report = str(valuation_raw or "")
            if valuation_report.strip():
                _set_cached_strategy_report(
                    company_name=company_name,
                    year=year,
                    report_type="valuation_anchor_report",
                    content=valuation_report
                )

            return {
                "indicator_extraction": [],
                "variable_table": [],
                "correlation_results": [],
                "strategy_conclusion": {"short_term": "", "long_term": "", "risk_control": "", "key_signals": []},
                "data_sufficiency": {
                    "is_sufficient": False,
                    "reason": "估值锚点模式不执行相关性/因子/聚类结构化分析",
                    "sample_description": None
                },
                "clustering_model": None,
                "notes": "估值锚点分析模式执行完成",
                "valuation_anchor_report": valuation_report.strip(),
                "model_type": "valuation_anchor",
                "company_name": company_name,
                "year": year
            }

        # 盈利预测模式：按五步框架直接生成报告，避免进入相关性/因子/聚类结构化链路
        if normalized_model == "earnings_forecast":
            quarterly_query = (
                f"{company_name} {year}年 季度 季报 单季 营业收入 净利润 EPS "
                "手续费及佣金净收入 业务及管理费 减值损失 毛利率 净利率"
            )
            guidance_query = (
                f"{company_name} {year}年 年报 管理层讨论与分析 前瞻 指引 展望 "
                "收入 成本 费用 风险 资产质量 分红 资本补充"
            )
            quarterly_data = query_engine.query(quarterly_query)
            guidance_data = query_engine.query(guidance_query)
            earnings_data = (
                f"【公司名称】{company_name}\n"
                f"【年份】{year}\n"
                f"【年报表格数据】\n{str(table_data)}\n\n"
                f"【年报正文数据】\n{str(report_data)}\n\n"
                f"【历史核心指标数据】\n{str(correlation_data)}\n\n"
                f"【季度数据（如有）】\n{str(quarterly_data)}\n\n"
                f"【管理层指引相关文本】\n{str(guidance_data)}"
            )
            earnings_prompt = f"""
你是一位专业的卖方分析师。请基于我上传的【公司名称】年报，完成以下盈利预测模型的搭建。

【公司名称】{company_name}
【报告年份】{year}

你可以使用以下检索到的原始数据：
{earnings_data}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第一步：提取历史财务数据
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

请从年报中精确提取以下数据（标注页码），填入表格：

【银行业版本】
| 项目 | 上年实际 | 本年实际 | 年报页码 |
|------|----------|----------|----------|
| 生息资产日均余额 | | | |
| 利息净收入 | | | |
| 非利息净收入 | | | |
|   手续费及佣金净收入 | | | |
|   其他非利息净收入 | | | |
| 营业收入 | | | |
| 业务及管理费 | | | |
| 减值损失前营业利润(PPOP) | | | |
| 信用及其他资产减值损失 | | | |
|   其中：贷款减值 | | | |
| 税前利润 | | | |
| 所得税费用 | | | |
| 归属净利润 | | | |
| 总股本 | | | |
| EPS | | | |

【非银行业通用版本】
| 项目 | 上年实际 | 本年实际 | 年报页码 |
|------|----------|----------|----------|
| 营业收入 | | | |
| 营业成本 | | | |
| 毛利润 | | | |
| 销售费用 | | | |
| 管理费用 | | | |
| 研发费用 | | | |
| 财务费用 | | | |
| 资产减值损失 | | | |
| 营业利润 | | | |
| 利润总额 | | | |
| 所得税费用 | | | |
| 归属净利润 | | | |
| 总股本 | | | |
| EPS | | | |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第二步：计算历史关键比率
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

请基于第一步数据，计算以下比率（写出计算公式和结果）：

【银行业】净息差、生息资产收益率、计息负债付息率、成本收入比、
信贷成本、有效税率、非息收入占比

【非银行业】毛利率、净利率、三费占比(销售/管理/研发各自占营收比)、
有效税率、ROE、ROA

同时提取季度数据（如有），计算最近两个季度的边际变化趋势。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第三步：提取管理层前瞻指引
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

请在年报的"管理层讨论与分析"章节中，找到管理层对以下方面的定性表述：
1. 收入/业务量展望（是否提及"增长""压力""企稳"等关键词）
2. 成本/费用展望（是否提及"降本增效""投入加大"等）
3. 风险/资产质量展望（是否提及"改善""承压""可控"等）
4. 资本/分红展望（是否提及"分红率""资本补充"等）

对每条表述，原文引用并标注页码。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第四步：构建三种情景假设
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

基于历史数据（第一、二步）和管理层指引（第三步），
对核心驱动变量设定悲观/中性/乐观三种假设值。

假设设定方法论（每个变量必须遵循）：
(a) 先确认该变量最近2-3年的历史趋势（方向和幅度）
(b) 再确认最近1-2个季度的边际变化（加速/减速/拐点）
(c) 再纳入管理层定性指引（对趋势的确认或修正）
(d) 综合(a)(b)(c)给出三种假设，并写出每个假设的一句话理由

【银行业核心变量】
| 变量 | 悲观 | 中性 | 乐观 | 假设依据 |
|------|------|------|------|----------|
| 净息差(NIM) | | | | |
| 生息资产增速 | | | | |
| 非息收入增速 | | | | |
| 成本收入比 | | | | |
| 信贷成本 | | | | |
| 有效税率 | | | | |

【非银行业核心变量】
| 变量 | 悲观 | 中性 | 乐观 | 假设依据 |
|------|------|------|------|----------|
| 营收增速 | | | | |
| 毛利率 | | | | |
| 销售费用率 | | | | |
| 管理费用率 | | | | |
| 研发费用率 | | | | |
| 有效税率 | | | | |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第五步：逐步推导预测利润表
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

用以下公式链，逐行推导三种情景下的预测值。
每一行必须写出：公式 → 代入数字 → 结果

【银行业推导链】
Step1: 预测生息资产 = 本年实际 × (1 + 生息资产增速假设)
Step2: 预测利息净收入 = NIM假设 × Step1
Step3: 预测非息净收入 = 本年实际 × (1 + 非息增速假设)
Step4: 预测营业收入 = Step2 + Step3
Step5: 预测业务管理费 = Step4 × CIR假设
Step6: 预测PPOP = Step4 - Step5
Step7: 预测减值损失 = 信贷成本假设 × 预测平均贷款 + 非贷款减值假设
Step8: 预测税前利润 = Step6 - Step7
Step9: 预测所得税 = Step8 × 有效税率假设
Step10: 预测归属净利润 = Step8 - Step9
Step11: 预测EPS = (Step10 - 优先股息等) / 总股本

【非银行业推导链】
Step1: 预测营收 = 本年实际 × (1 + 营收增速假设)
Step2: 预测毛利润 = Step1 × 毛利率假设
Step3: 预测销售费用 = Step1 × 销售费用率假设
Step4: 预测管理费用 = Step1 × 管理费用率假设
Step5: 预测研发费用 = Step1 × 研发费用率假设
Step6: 预测营业利润 = Step2 - Step3 - Step4 - Step5 - 财务费用等
Step7: 预测税前利润 ≈ Step6 ± 营业外
Step8: 预测所得税 = Step7 × 有效税率假设
Step9: 预测归属净利润 = Step7 - Step8
Step10: 预测EPS = Step9 / 总股本

最终输出三种情景下的：预测营收、预测净利润、预测EPS、
营收同比增速、净利润同比增速。

输出格式要求：
1. 使用 Markdown 输出完整报告。
2. 缺失值要明确写“未披露/无法确认”，不得编造。
3. 每个引用尽可能带“年报页码”；若检索信息无页码，请标注“页码待核实”。
"""

            earnings_raw = await llm.achat([
                ChatMessage(role="system", content="你是专业卖方分析师，擅长年报盈利预测。请严格按五步输出，优先可追溯与可计算性。"),
                ChatMessage(role="user", content=earnings_prompt)
            ])
            if hasattr(earnings_raw, "message") and hasattr(earnings_raw.message, "content"):
                earnings_report = earnings_raw.message.content or ""
            else:
                earnings_report = str(earnings_raw or "")
            if earnings_report.strip():
                _set_cached_strategy_report(
                    company_name=company_name,
                    year=year,
                    report_type="earnings_forecast_report",
                    content=earnings_report
                )

            # 调试日志：逐步打印 + 表格结构检查（仅定位问题，不改变业务输出）
            try:
                report_text = earnings_report.strip()
                regex = __import__("re")
                logger.info("🧪 [earnings_forecast][debug] 报告总长度=%s", len(report_text))

                step_titles = [
                    "第一步：提取历史财务数据",
                    "第二步：计算历史关键比率",
                    "第三步：提取管理层前瞻指引",
                    "第四步：构建三种情景假设",
                    "第五步：逐步推导预测利润表",
                ]
                positions = []
                for title in step_titles:
                    match = regex.search(regex.escape(title), report_text)
                    if match:
                        positions.append((title, match.start()))
                    else:
                        logger.warning("⚠️ [earnings_forecast][debug] 未找到步骤标题: %s", title)
                positions.sort(key=lambda item: item[1])

                def _split_pipe_cells(line: str) -> List[str]:
                    t = (line or "").strip()
                    if not (t.startswith("|") and t.endswith("|")):
                        return []
                    return [cell.strip() for cell in t[1:-1].split("|")]

                def _is_divider(line: str) -> bool:
                    return bool(regex.match(r"^\|[\s\-:|]+\|$", (line or "").strip()))

                for idx, (title, start) in enumerate(positions):
                    end = positions[idx + 1][1] if idx + 1 < len(positions) else len(report_text)
                    section = report_text[start:end].strip()
                    lines = section.splitlines()
                    logger.info(
                        "🧪 [earnings_forecast][debug][%s] 字符数=%s, 行数=%s, 预览=%s",
                        title,
                        len(section),
                        len(lines),
                        section[:600].replace("\n", "\\n")
                    )

                    # 表格结构检查：检测每个 markdown 表的列数一致性
                    i = 0
                    table_index = 0
                    while i < len(lines):
                        header = (lines[i] or "").strip()
                        divider = (lines[i + 1] or "").strip() if i + 1 < len(lines) else ""
                        if header.startswith("|") and header.endswith("|") and _is_divider(divider):
                            table_index += 1
                            header_cells = _split_pipe_cells(header)
                            expected_cols = len(header_cells)
                            logger.info(
                                "🧪 [earnings_forecast][debug][%s][表%s] 表头列数=%s, 表头=%s",
                                title,
                                table_index,
                                expected_cols,
                                header[:240]
                            )
                            i += 2
                            row_no = 0
                            while i < len(lines):
                                row_line = (lines[i] or "").strip()
                                if not row_line:
                                    i += 1
                                    continue
                                if not (row_line.startswith("|") and row_line.endswith("|")):
                                    # 非管道行可能是“断行补尾”，重点打印
                                    logger.warning(
                                        "⚠️ [earnings_forecast][debug][%s][表%s] 遇到非表格行(疑似断行): %s",
                                        title,
                                        table_index,
                                        row_line[:240]
                                    )
                                    break
                                row_no += 1
                                row_cells = _split_pipe_cells(row_line)
                                cell_count = len(row_cells)
                                if cell_count != expected_cols:
                                    logger.warning(
                                        "⚠️ [earnings_forecast][debug][%s][表%s][行%s] 列数不一致: 期望=%s, 实际=%s, 内容=%s",
                                        title,
                                        table_index,
                                        row_no,
                                        expected_cols,
                                        cell_count,
                                        row_line[:240]
                                    )
                                else:
                                    logger.info(
                                        "🧪 [earnings_forecast][debug][%s][表%s][行%s] 列数正常=%s",
                                        title,
                                        table_index,
                                        row_no,
                                        cell_count
                                    )
                                if regex.search(r"\d{1,3},\d{3}", row_line):
                                    logger.warning(
                                        "⚠️ [earnings_forecast][debug][%s][表%s][行%s] 检测到千分位逗号，可能影响渲染: %s",
                                        title,
                                        table_index,
                                        row_no,
                                        row_line[:240]
                                    )
                                i += 1
                            continue
                        i += 1
            except Exception as debug_err:
                logger.warning("⚠️ [earnings_forecast][debug] 调试日志生成失败: %s", str(debug_err))

            return {
                "indicator_extraction": [],
                "variable_table": [],
                "correlation_results": [],
                "strategy_conclusion": {"short_term": "", "long_term": "", "risk_control": "", "key_signals": []},
                "data_sufficiency": {
                    "is_sufficient": False,
                    "reason": "盈利预测模式不执行相关性/因子/聚类结构化分析",
                    "sample_description": None
                },
                "clustering_model": None,
                "notes": "盈利预测模式执行完成",
                "earnings_forecast_report": earnings_report.strip(),
                "model_type": "earnings_forecast",
                "company_name": company_name,
                "year": year
            }

        # 仅聚类模式：跳过指标抽取与相关性/因子，只执行聚类
        if normalized_model == "clustering":
            logger.info("仅生成聚类分析，跳过指标抽取与相关性/因子步骤")
            result_dict = {
                "indicator_extraction": [],
                "variable_table": [],
                "correlation_results": [],
                "strategy_conclusion": {"short_term": "", "long_term": "", "risk_control": "", "key_signals": []},
                "data_sufficiency": {"is_sufficient": False, "reason": "仅聚类模式，未执行指标抽取", "sample_description": None},
                "notes": "",
                "company_name": company_name,
                "year": year,
            }
        else:
            prompt = f"""
作为资深投资分析师，请基于以下数据，为{company_name}生成"投资策略分析"的指标抽取与结构化数据。

## 数据来源
以下数据来自年报披露与相关指标说明：

{str(forecast_data)}

## 核心任务：多维度数据提取

你需要从年报中提取**多个维度的结构化数据**，以支持后续的统计分析（相关性分析、多元线性回归、聚类分析、因子分析）。

### 1. 指标自动识别与抽取（多维度提取）

请从年报中识别并抽取以下**多个维度**的指标数据。**相关性分析要求至少近三年的数据**，不同年份的指标在命名和单位上保持一致。

#### 维度1：核心财务指标（用于相关性分析及投资策略，至少三年）
**相关性分析必选指标（须至少覆盖近三年）**：
- **净息差**（NIM）
- **ROE**（净资产收益率）
- **ROA**（资产净利率）
- **不良率**（不良贷款率）
- **拨备覆盖率**（投资覆盖率）
- **成本收入比**
- **信贷成本**
- **资本充足率**（或核心一级资本充足率）

其他可选指标（用于多元回归、聚类等）：
- 收益类（因变量）：股息率、分红率
- 盈利类：非息收入增速、净利息收入、手续费及佣金净收入
- 业务类：零售贷款增速、对公贷款增速、零售存款增速、对公存款增速
- 估值类：市净率（PB）、市盈率（PE）、总市值
- 风险敞口类：房地产敞口不良率、房地产贷款占比

#### 维度2：贷款产品维度（用于聚类和相关性分析）
从年报中查找贷款产品分类表，提取：
- 产品名称（如：住房按揭、一般企业贷款、信用卡、消费贷、经营贷、贴现等）
- 每个产品的：余额、占比、不良率、余额变动率、增速
- 如果年报中有多个年份数据，一并提取

#### 维度3：地区经营维度（用于因子分析和聚类）
从年报中查找地区经营数据，提取：
- 地区名称（如：东区、南区、西区、北区、总部、境外等）
- 每个地区的：贷款余额、存款余额、存贷比、不良率、贷款占比、存款占比

#### 维度4：行业贷款分布（用于聚类分析）
从年报中查找行业贷款分布表，提取：
- 行业名称（如：制造业、房地产业、批发零售业等）
- 每个行业的：贷款余额、占比、不良率

#### 维度5：业务板块数据（用于相关性分析）
从年报中查找业务板块数据，提取：
- 板块名称（如：零售银行、对公银行、资金业务等）
- 每个板块的：营业收入、净利润、资产规模、减值损失

#### 维度6：资产负债结构（用于因子分析）
从年报中查找资产负债结构表，提取：
- 资产/负债科目名称
- 每个科目的：日均余额、利息收入/支出、平均收益率/成本率、变动率

#### 维度7：时间序列数据（至少三年，用于相关性分析）
**必须**：尽量提取至少**近三年**的年度数据，以便准确计算 Pearson 相关系数和趋势。
- 年度指标：净息差、ROE、ROA、不良率、拨备覆盖率、成本收入比、信贷成本、资本充足率，以及营业收入、净利润、总资产等
- 确保不同年份的指标命名与单位一致，避免分析误差
- 季度数据（若有）：各季度的收入、利润、现金流

### 2. 数据提取要求

1. **优先从表格中提取**：年报中的表格数据最准确，优先使用表格数据
2. **补充文本数据**：如果表格中没有，尝试从文本描述中提取
3. **保持原始精度**：保留原始数值，不要四舍五入
4. **标注数据来源**：记录每个指标在年报中的位置（如"第X页表格"或"管理层讨论与分析"）
5. **处理缺失值**：如果某个指标缺失，标注为null，不要编造数据

### 3. 输入变量表构建

将提取的指标整理为"输入变量表"，包括：
- variable_type：变量类型（收益类/盈利类/风险类/业务类/估值类/风险敞口类/其他）
- metric：具体指标名称
- value：指标取值（数值）
- period：期间（年份）
- unit：单位（%、亿元、万元等）

**相关性分析强制要求**：对于以下 8 项核心指标——净息差、ROE、ROA、不良率、拨备覆盖率、成本收入比、信贷成本、资本充足率——**必须在 variable_table 中为每项指标填写至少三年的数据**（即同一 metric 多行，每行一个年份的 period 与 value）。例如：净息差 2022/2.5%、2023/2.4%、2024/2.3% 应占 3 行。若年报仅有两年或一年，则如实填写已有年份，以便后续步骤尽量计算或做定性分析。其他维度若有多个观测值（如多个产品、多个地区），每个观测值单独记录一行。

### 4. 输出要求（不要生成分析结果）

- "correlation_results"必须输出空数组[]（由后续 LLM 生成）
- "strategy_conclusion"中的字段保持为空字符串或空数组（由后续 LLM 生成）
- "clustering_model"保持为null（由后续 LLM 生成）
- "factor_analysis"保持为null（由后续 LLM 生成）

## ⚠️ 严格输出要求（必须遵守）
你必须输出一个有效的JSON对象，且仅输出JSON，不要有任何其他文字说明。

### JSON格式要求：
1. 必须是有效的JSON格式，可以直接被JSON.parse()解析
2. 不要使用markdown代码块（不要用```json包裹）
3. 不要有任何前缀或后缀文字
4. 直接输出JSON对象，从{{开始，以}}结束
5. 所有字符串值必须用双引号包裹
6. 所有数字和布尔值不要用引号
7. 确保所有必需字段都存在

### JSON结构（必须严格遵循）：
{{
  "indicator_extraction": [
    {{
      "name": "指标名称",
      "category": "收益类/盈利类/风险类/业务类/估值类/风险敞口类/其他",
      "variable_role": "因变量/自变量",
      "value": "指标取值",
      "unit": "%",
      "period": "2024",
      "source_excerpt": "来源片段"
    }}
  ],
  "variable_table": [
    {{
      "variable_type": "收益类（因变量）",
      "metric": "股息率",
      "value": "5.1",
      "period": "2024",
      "unit": "%"
    }}
  ],
  "correlation_results": [],
  "strategy_conclusion": {{
    "short_term": "",
    "long_term": "",
    "risk_control": "",
    "key_signals": []
  }},
  "data_sufficiency": {{
    "is_sufficient": false,
    "reason": null,
    "sample_description": null
  }},
  "notes": "补充说明（可选）"
}}

### 重要提示：
- 如果数据缺失，使用null或空数组[]
- 所有字段都必须存在，不能省略
- correlation_results必须保持空数组[]
- **严格控制输出长度**：indicator_extraction 与 variable_table 优先列出相关性分析所需的 8 项核心指标（净息差、ROE、ROA、不良率、拨备覆盖率、成本收入比、信贷成本、资本充足率）及至少三年数据，其余维度可精简，避免输出过长导致 JSON 语法错误（如漏逗号、括号不匹配）。
- 直接输出上述JSON结构，不要有任何其他内容
"""

        # 仅当非“仅聚类”模式时执行指标抽取 LLM
        if normalized_model != "clustering":
            # 使用结构化输出 - 添加异常处理和性能监控
            response = None
            import time
            structured_llm_start = time.time()
            try:
                sllm = llm.as_structured_llm(ProfitForecastAndValuation)
                raw_response = await sllm.achat([
                    ChatMessage(role="system", content="你是一个专业的投资分析师,擅长相关性分析与投资策略。你必须严格按照用户要求的JSON格式输出，只输出JSON，不要有任何其他文字。"),
                    ChatMessage(role="user", content=prompt)
                ])
                # 检查响应类型 - 处理字符串响应
                if isinstance(raw_response, str):
                    logger.warning(f"⚠️ [generate_profit_forecast_and_valuation] 结构化LLM返回字符串，尝试解析JSON")
                    import json
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', raw_response)
                    if json_match:
                        parsed_data = json.loads(json_match.group(0))
                        if 'investment_strategy' in parsed_data or 'profit_forecast_and_valuation' in parsed_data:
                            parsed_data = parsed_data.get('investment_strategy') or parsed_data.get('profit_forecast_and_valuation') or parsed_data
                        response = ProfitForecastAndValuation(**parsed_data) if isinstance(parsed_data, dict) and 'indicator_extraction' in parsed_data else parsed_data
                    else:
                        raise ValueError("无法从字符串响应提取JSON")
                elif isinstance(raw_response, ProfitForecastAndValuation):
                    response = raw_response
                elif hasattr(raw_response, 'message') and hasattr(raw_response.message, 'content'):
                    content = raw_response.message.content
                    if isinstance(content, str):
                        logger.warning(f"⚠️ [generate_profit_forecast_and_valuation] 响应message.content是字符串，尝试解析JSON")
                        import json
                        import re
                        json_match = re.search(r'\{[\s\S]*\}', content)
                        if json_match:
                            parsed_data = json.loads(json_match.group(0))
                            if 'investment_strategy' in parsed_data or 'profit_forecast_and_valuation' in parsed_data:
                                parsed_data = parsed_data.get('investment_strategy') or parsed_data.get('profit_forecast_and_valuation') or parsed_data
                            response = ProfitForecastAndValuation(**parsed_data) if isinstance(parsed_data, dict) and 'indicator_extraction' in parsed_data else parsed_data
                        else:
                            raise ValueError("无法从message.content提取JSON")
                    else:
                        response = content
                else:
                    response = raw_response
                structured_llm_time = time.time() - structured_llm_start
                logger.info(f"✅ [generate_profit_forecast_and_valuation] 结构化输出成功，耗时: {structured_llm_time:.2f}秒")
            except (AttributeError, ValueError, TypeError) as structured_error:
                error_type = type(structured_error).__name__
                error_msg = str(structured_error)
                structured_llm_time = time.time() - structured_llm_start
                if "model_dump_json" in error_msg or "AttributeError" in error_type:
                    logger.warning(f"⚠️ [generate_profit_forecast_and_valuation] 结构化LLM返回了字符串而非Pydantic模型（耗时: {structured_llm_time:.2f}秒）")
                    logger.warning(f"[generate_profit_forecast_and_valuation] 错误类型: {error_type}, 错误信息: {error_msg}")
                    logger.info(f"[generate_profit_forecast_and_valuation] 这是LlamaIndex的已知问题，将尝试从字符串解析JSON")
                else:
                    logger.warning(f"⚠️ [generate_profit_forecast_and_valuation] 结构化输出失败（{error_type}，耗时: {structured_llm_time:.2f}秒）: {error_msg}")
                logger.info(f"[generate_profit_forecast_and_valuation] 尝试使用普通LLM输出并手动解析JSON")
                try:
                    normal_response = await llm.achat([
                        ChatMessage(role="system", content="你是一个专业的投资分析师,擅长相关性分析与投资策略。你必须严格按照用户要求的JSON格式输出，只输出JSON，不要有任何其他文字。"),
                        ChatMessage(role="user", content=prompt)
                    ])
                    if hasattr(normal_response, 'message'):
                        content = normal_response.message.content if hasattr(normal_response.message, 'content') else str(normal_response.message)
                    else:
                        content = str(normal_response)
                    import json
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', content)
                    if json_match:
                        json_str = json_match.group(0)
                        parsed_data = json.loads(json_str)
                        if isinstance(parsed_data, dict):
                            if 'investment_strategy' in parsed_data or 'profit_forecast_and_valuation' in parsed_data:
                                parsed_data = parsed_data.get('investment_strategy') or parsed_data.get('profit_forecast_and_valuation') or parsed_data
                            elif len(parsed_data) == 1:
                                first_val = list(parsed_data.values())[0]
                                parsed_data = first_val if isinstance(first_val, dict) else parsed_data
                        if isinstance(parsed_data, dict) and ('indicator_extraction' in parsed_data or 'variable_table' in parsed_data):
                            try:
                                response = ProfitForecastAndValuation(**parsed_data)
                                logger.info(f"✅ 手动解析JSON成功")
                            except Exception as validation_error:
                                logger.warning(f"⚠️ JSON验证失败，返回部分数据: {str(validation_error)}")
                                response = parsed_data
                        else:
                            raise ValueError("无法从响应中提取有效结构（缺少 indicator_extraction 或 variable_table）")
                    else:
                        raise ValueError("无法从响应中提取JSON")
                except Exception as fallback_error:
                    logger.error(f"❌ 回退方案也失败: {str(fallback_error)}")
                    response = {
                        "error": f"生成失败: {str(fallback_error)}",
                        "content": content if 'content' in locals() else str(fallback_error)
                    }

            logger.info(f"✅ 投资策略（指标抽取）生成成功")
            # 处理响应 - 确保返回字典格式
            result_dict = None
            if isinstance(response, dict) and 'error' in response:
                result_dict = response
            elif isinstance(response, ProfitForecastAndValuation):
                result_dict = response.model_dump()
            elif hasattr(response, 'raw'):
                raw_data = response.raw
                if hasattr(raw_data, 'model_dump'):
                    try:
                        result_dict = raw_data.model_dump()
                    except Exception as e:
                        logger.warning(f"model_dump() 失败: {e}")
                elif isinstance(raw_data, dict):
                    result_dict = raw_data
                elif isinstance(raw_data, str):
                    import json
                    try:
                        result_dict = json.loads(raw_data)
                    except json.JSONDecodeError:
                        result_dict = {"content": raw_data}
                else:
                    result_dict = {"content": str(raw_data)}
            if result_dict is None:
                if hasattr(response, 'model_dump'):
                    try:
                        result_dict = response.model_dump()
                    except Exception:
                        pass
                elif isinstance(response, dict):
                    result_dict = response
                else:
                    result_dict = {"content": str(response)}
            if not isinstance(result_dict, dict):
                result_dict = {"content": str(result_dict)}
            result_dict["company_name"] = company_name
            result_dict["year"] = year

        # 若首轮指标抽取失败（返回了 error），直接返回错误，不执行后续分析
        if isinstance(result_dict, dict) and result_dict.get("error"):
            logger.warning(f"⚠️ 指标抽取或解析失败，跳过后续分析: {result_dict.get('error')}")
            return result_dict
        
        # 数据验证和清理
        result_dict = _validate_and_clean_data(result_dict, ProfitForecastAndValuation)
        if isinstance(result_dict, dict):
            data_sufficiency = result_dict.get("data_sufficiency")
            if isinstance(data_sufficiency, dict) and not isinstance(data_sufficiency.get("is_sufficient"), bool):
                data_sufficiency["is_sufficient"] = False

        # 自动执行：相关性分析、聚类、因子分析（支持单模块：correlation_only, factor_only；已去掉多元回归）
        if isinstance(result_dict, dict):
            result_dict.setdefault("card_insights", {})
            # 1. 相关性分析
            if normalized_model in {"correlation", "all", "correlation_only"}:
                correlation_results = result_dict.get("correlation_results") or []
                data_sufficiency = result_dict.get("data_sufficiency")
                if not correlation_results:
                    logger.info("使用 LLM 执行相关性分析")
                    computed_results, computed_sufficiency = await _llm_correlation_analysis(
                        result_dict.get("indicator_extraction") or [],
                        result_dict.get("variable_table") or [],
                        year,
                        llm
                    )
                    result_dict["correlation_results"] = computed_results
                    result_dict["data_sufficiency"] = data_sufficiency or computed_sufficiency
                elif not data_sufficiency:
                    _, computed_sufficiency = await _llm_correlation_analysis(
                        result_dict.get("indicator_extraction") or [],
                        result_dict.get("variable_table") or [],
                        year,
                        llm
                    )
                    result_dict["data_sufficiency"] = computed_sufficiency

                # 基于计算结果生成洞察（只做结论，不再生成数值）
                strategy_conclusion = result_dict.get("strategy_conclusion") or {}
                has_conclusion = any([
                    bool(strategy_conclusion.get("short_term")),
                    bool(strategy_conclusion.get("long_term")),
                    bool(strategy_conclusion.get("risk_control")),
                    bool(strategy_conclusion.get("key_signals"))
                ])
                if not has_conclusion:
                    import json
                    insight_prompt = f"""
你是专业投资分析师。请按以下流程生成**相关性分析报告的关键结论与洞察总结**，并**务必输出四类内容**，不得出现"无法生成"、"无法进行"、"无法识别"等消极表述。

## 输入数据

### Pearson 相关系数结果（两两配对，可能为空）
{json.dumps(result_dict.get("correlation_results") or [], ensure_ascii=False)}

### 数据充分性
{json.dumps(result_dict.get("data_sufficiency") or {}, ensure_ascii=False)}

### 输入变量表（指标与多年取值）
{json.dumps(result_dict.get("variable_table") or [], ensure_ascii=False)}

## 执行要求

**步骤 3：关键结论生成**  
基于 Pearson 相关系数矩阵（若不为空）或基于**输入变量表中的指标数值 + 行业常识**，生成以下四类内容：

1. **高相关性指标**（short_term）：若相关系数结果非空，列出相关系数绝对值较高的指标对及业务含义；若为空，则根据变量表与银行业常识（如净息差与ROE通常正相关、ROA与ROE联动等）写出定性结论。
2. **低相关性指标**（risk_control）：若相关系数结果非空，列出无显著相关或相关性很弱的指标对及风险提示；若为空，则根据常识说明哪些指标间通常关联较弱（如资本充足率与不良率）及需关注的其他风险因素。
3. **趋势分析**（long_term）：若有多年数据或相关系数，说明指标间联动趋势与长期投资启示；若数据有限，则基于变量表已有年度与行业规律做简要趋势判断。
4. **步骤 4：洞察总结**（key_signals）：用**示例句式**写出 2～4 条洞察句，每条说明一对指标之间的关系及投资含义。必须包含类似以下的表述风格（可结合实际数据调整）：
   - "净息差与ROE呈现高度正相关，说明银行的盈利能力和息差变化紧密相关。"
   - "信贷成本与成本收入比呈负相关，这意味着信贷成本较高时，银行可能面临更高的运营成本。"
   - "资本充足率与不良率没有显著相关性，需关注其他潜在风险因素。"

若相关系数结果为空或数据不足，在 notes 中可注明"部分结论基于有限数据或行业经验的定性分析"，但 short_term、long_term、risk_control、key_signals 四类内容仍须全部填写，不得留空或写"无法生成"。

必须只输出一个 JSON 对象，结构如下：
{{
  "strategy_conclusion": {{
    "short_term": "高相关性指标描述（指标对+业务含义）",
    "long_term": "趋势分析（联动趋势与长期启示）",
    "risk_control": "低相关性指标与风险提示",
    "key_signals": ["洞察句1", "洞察句2", "洞察句3"]
  }},
  "notes": "补充说明（可选）"
}}
"""
                    try:
                        insight_response = await llm.achat([
                            ChatMessage(role="system", content="你是一个专业的投资分析师，擅长相关性分析后的策略总结。你必须只输出JSON。"),
                            ChatMessage(role="user", content=insight_prompt)
                        ])
                        if hasattr(insight_response, 'message'):
                            insight_content = insight_response.message.content if hasattr(insight_response.message, 'content') else str(insight_response.message)
                        else:
                            insight_content = str(insight_response)
                        import re
                        json_match = re.search(r'\{[\s\S]*\}', insight_content)
                        if json_match:
                            parsed = json.loads(json_match.group(0))
                            conclusion = parsed.get("strategy_conclusion") if isinstance(parsed, dict) else None
                            if isinstance(conclusion, dict):
                                result_dict["strategy_conclusion"] = {
                                    "short_term": conclusion.get("short_term") or "",
                                    "long_term": conclusion.get("long_term") or "",
                                    "risk_control": conclusion.get("risk_control") or "",
                                    "key_signals": conclusion.get("key_signals") or []
                                }
                            if isinstance(parsed, dict) and parsed.get("notes"):
                                result_dict["notes"] = parsed.get("notes")
                    except Exception as insight_error:
                        logger.warning(f"⚠️ [generate_profit_forecast_and_valuation] 洞察生成失败: {str(insight_error)}")

                # 与洞察同时生成相关性分析可视化视图（供前端以卡片形式展示在可视化视图界面）
                corr_results = result_dict.get("correlation_results") or []
                if corr_results:
                    try:
                        metrics_ordered = []
                        seen = set()
                        for r in corr_results:
                            for m in (r.get("target_metric"), r.get("driver_metric")):
                                if m and m not in seen:
                                    seen.add(m)
                                    metrics_ordered.append(m)
                        n = len(metrics_ordered)
                        metric_to_idx = {m: i for i, m in enumerate(metrics_ordered)}
                        z_matrix = [[None] * n for _ in range(n)]
                        for r in corr_results:
                            t = r.get("target_metric")
                            d = r.get("driver_metric")
                            c = r.get("correlation")
                            if t is None or d is None or c is None:
                                continue
                            i = metric_to_idx.get(t)
                            j = metric_to_idx.get(d)
                            if i is not None and j is not None:
                                z_matrix[i][j] = round(float(c), 3)
                                z_matrix[j][i] = round(float(c), 3)
                        for i in range(n):
                            if z_matrix[i][i] is None:
                                z_matrix[i][i] = 1.0
                        result_dict["correlation_visualization"] = {
                            "has_visualization": True,
                            "visualization_type": "plotly",
                            "chart_config": {
                                "chart_type": "heatmap",
                                "traces": [
                                    {
                                        "type": "heatmap",
                                        "z": z_matrix,
                                        "x": metrics_ordered,
                                        "y": metrics_ordered,
                                        "colorscale": [[0, "#ef4444"], [0.5, "#fbbf24"], [1, "#10b981"]],
                                        "zmin": -1,
                                        "zmax": 1
                                    }
                                ],
                                "layout": {
                                    "title": "相关性分析热力图",
                                    "xaxis_title": "",
                                    "yaxis_title": "",
                                    "height": 420
                                }
                            }
                        }
                        logger.info("✅ 相关性分析可视化视图已生成")
                    except Exception as viz_err:
                        logger.warning(f"⚠️ [generate_profit_forecast_and_valuation] 相关性可视化构建失败: {str(viz_err)}")

            else:
                result_dict["correlation_results"] = []
                result_dict["strategy_conclusion"] = {
                    "short_term": "",
                    "long_term": "",
                    "risk_control": "",
                    "key_signals": []
                }
                result_dict["data_sufficiency"] = {
                    "is_sufficient": False,
                    "reason": "相关性模型未启用",
                    "sample_description": None
                }
            
            # 2. 因子分析（LLM）
            if normalized_model in {"correlation", "all", "factor_only"}:
                if not result_dict.get("factor_analysis"):
                    logger.info("使用 LLM 执行因子分析")
                    factor_result, factor_sufficiency = await _llm_factor_analysis(
                        result_dict.get("indicator_extraction") or [],
                        result_dict.get("variable_table") or [],
                        year,
                        llm
                    )
                    result_dict["factor_analysis"] = factor_result
                    if not result_dict.get("factor_data_sufficiency"):
                        result_dict["factor_data_sufficiency"] = factor_sufficiency

            # 4. 生成聚类分析模型（规模—风险—增长 K-Means，可解释可决策）
            if normalized_model in {"clustering", "all"} and not result_dict.get("clustering_model"):
                import json
                clustering_prompt = f"""
你必须严格按照以下步骤执行聚类分析，并在最后只输出一个合法的 JSON 对象（见步骤七），不要输出 JSON 以外的任何文字、markdown 代码块或说明。系统会直接解析你回复中的 JSON。

## 数据来源（年报与表格）
以下数据来自年报披露与相关指标，请据此提取并分析：
{str(forecast_data)}

---

一、明确聚类目标（必须先做）
在内部推理中说明：本次聚类对象（如贷款类别/业务分部/产品线）、聚类目的（规模分层、风险分层、增长分层、战略取舍、结构优化、投资决策支持之一或组合）。

二、原始数据整理
从年报中提取横向可比数据，至少包含：规模类（余额/收入/资产或占比）、风险质量类（不良率/违约率/毛利率等）、成长性（同比/环比/CAGR）。在推理中整理成表格式。

三、数据标准化处理
对数值做标准化（Min-Max 或 Z-score），在推理中给出标准化表示例；若某指标完全相同则说明对聚类贡献有限。

四、执行 K-Means 聚类
在推理中说明采用的 k 值及聚类过程。

五、业务语义命名（关键步骤）
为每个 Cluster 赋予业务含义标签（如：增长型核心资产、稳健基石资产、收缩调整资产等），不得只写 Cluster 1/2/3，并说明命名逻辑。

六、聚类结果汇总
在推理中完成：聚类与成员、规模/风险/增长特征、战略含义；分析哪类是增长引擎、稳定器、需压降或调整，是否存在资源错配。

七、结构化 JSON 输出（你必须执行的最后一步）
你的回复中必须且只能包含一个 JSON 对象，严禁在 JSON 前后添加任何说明、标题或 ```json 等标记。结构必须如下，将聚类结果放在 "clustering_model" 键下：
{{
  "clustering_model": {{
    "method": "k-means",
    "k": 3,
    "dimensions": ["规模", "风险", "增长"],
    "clusters": [
      {{
        "name": "业务含义标签（如：增长型核心资产）",
        "members": ["成员1", "成员2"],
        "characteristics": "规模/风险/增长特征描述",
        "strategy_implication": "战略含义"
      }}
    ],
    "core_insights": ["核心发现1", "核心发现2"],
    "risk_notes": ["风险提示1", "风险提示2"]
  }}
}}
- core_insights：3–5 条核心发现（结论+简短解释），例如：高风险业务是否收缩、规模最大板块是否增长放缓、低风险板块是否承担稳定器、战略与资源分布是否匹配。
- risk_notes：1–3 条风险提示。
- clusters 内 name、members、characteristics、strategy_implication 均需根据步骤一至六的推理结果填写，不要留空。

八、执行要求
请先按步骤一至六在内部完成推理与数据整理，然后只输出步骤七中的 JSON 对象，不要输出步骤一至六的中间文字。现在请直接输出 JSON。
"""
                try:
                    clustering_response = await llm.achat([
                        ChatMessage(role="system", content="你是专业投研分析师，专门执行 K-Means 聚类（规模—风险—增长）。你必须严格按用户给出的步骤一至八执行：在内部完成步骤一至六的推理与数据整理，最后只输出一个合法的 JSON 对象（包含 clustering_model 键）。禁止输出 JSON 以外的任何内容（包括说明、markdown、代码块标记）。"),
                        ChatMessage(role="user", content=clustering_prompt)
                    ])
                    if hasattr(clustering_response, 'message'):
                        clustering_content = clustering_response.message.content if hasattr(clustering_response.message, 'content') else str(clustering_response.message)
                    else:
                        clustering_content = str(clustering_response)
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', clustering_content)
                    if json_match:
                        # 去掉 JSON 字符串内的控制字符（如未转义换行），避免 Invalid control character 解析错误
                        json_str = re.sub(r'[\x00-\x1f]', ' ', json_match.group(0))
                        parsed = json.loads(json_str)
                        clustering_model = parsed.get("clustering_model") if isinstance(parsed, dict) else None
                        if isinstance(clustering_model, dict):
                            # 若为新版结构（clusters + core_insights），兼容旧版 group_results / conclusion
                            clusters = clustering_model.get("clusters") or []
                            if clusters and not clustering_model.get("group_results"):
                                clustering_model["group_results"] = [
                                    {
                                        "group_name": c.get("name", ""),
                                        "feature_profile": c.get("characteristics", ""),
                                        "company_assignment": "",
                                        "investor_profile": "",
                                        "time_risk_bucket": c.get("strategy_implication", "")
                                    }
                                    for c in clusters if isinstance(c, dict)
                                ]
                            if not clustering_model.get("conclusion"):
                                core_insights = clustering_model.get("core_insights") or []
                                risk_notes = clustering_model.get("risk_notes") or []
                                clustering_model["conclusion"] = {
                                    "current_position": core_insights[0] if core_insights else "",
                                    "upgrade_conditions": core_insights[1] if len(core_insights) > 1 else "",
                                    "high_growth_conditions": risk_notes[0] if risk_notes else ""
                                }
                            if not clustering_model.get("variable_table") and clusters:
                                dims = clustering_model.get("dimensions") or ["规模", "风险", "增长"]
                                clustering_model["variable_table"] = [{"dimension": d, "metric": d, "company_value": "", "industry_benchmark": ""} for d in dims]
                            result_dict["clustering_model"] = clustering_model
                except Exception as clustering_error:
                    logger.warning(f"⚠️ [generate_profit_forecast_and_valuation] 聚类模型生成失败: {str(clustering_error)}")
            
            # 为可视化卡片生成数据洞察（LLM 二次生成，每条 80 字以内完整句，不截断）
            has_correlation = bool(result_dict.get("correlation_results") or result_dict.get("correlation_visualization"))
            has_factor = bool(result_dict.get("factor_analysis") and (result_dict.get("factor_analysis") or {}).get("factors"))
            has_clustering = bool(result_dict.get("clustering_model"))
            import json as _json
            card_insights = {
                "correlation_summary": "",
                "factor_summary": "",
                "clustering_summary": "",
            }
            if has_correlation or has_factor or has_clustering:
                try:
                    card_insight_prompt = f"""你是专业投资分析师。请根据下方「数据」中已有的分析结果，为前端可视化卡片生成数据洞察。

要求：
1. 每条洞察**严格控制在 80 字以内**，由你**直接生成**符合字数的完整句子，**禁止先写长文再截断、禁止使用省略号**。
2. 仅根据给出的数据撰写，不要编造数字。
3. 若某部分无数据，对应字段输出空字符串 ""。

输出**唯一**一个 JSON 对象，不要 markdown 代码块或其它说明：
{{"correlation_summary": "…", "factor_summary": "…", "clustering_summary": "…"}}

数据：
"""
                    if has_correlation:
                        card_insight_prompt += f"\n【相关性】\n{_json.dumps(result_dict.get('correlation_results') or [], ensure_ascii=False)}\n策略结论摘要：{_json.dumps(result_dict.get('strategy_conclusion') or {}, ensure_ascii=False)}\n"
                    if has_factor:
                        card_insight_prompt += f"\n【因子分析】\n{_json.dumps(result_dict.get('factor_analysis') or {}, ensure_ascii=False)}\n"
                    if has_clustering:
                        card_insight_prompt += f"\n【聚类分析】\n{_json.dumps(result_dict.get('clustering_model') or {}, ensure_ascii=False)}\n"
                    card_insight_prompt += "\n请直接输出上述 JSON，且每条 summary 为 80 字以内的完整句，禁止截断或省略号。"
                    card_response = await llm.achat([
                        ChatMessage(role="system", content="你只输出一个 JSON 对象，包含 correlation_summary、factor_summary、clustering_summary。每条 80 字以内完整句，禁止截断或省略号。"),
                        ChatMessage(role="user", content=card_insight_prompt)
                    ])
                    if hasattr(card_response, 'message'):
                        card_content = card_response.message.content if hasattr(card_response.message, 'content') else str(card_response.message)
                    else:
                        card_content = str(card_response)
                    _json_match = re.search(r'\{[\s\S]*\}', card_content)
                    if _json_match:
                        card_parsed = _json.loads(_json_match.group(0))
                        card_insights["correlation_summary"] = (card_parsed.get("correlation_summary") or "").strip()
                        card_insights["factor_summary"] = (card_parsed.get("factor_summary") or "").strip()
                        card_insights["clustering_summary"] = (card_parsed.get("clustering_summary") or "").strip()
                        logger.info("✅ 可视化卡片数据洞察已生成")
                except Exception as card_err:
                    logger.warning(f"⚠️ [generate_profit_forecast_and_valuation] 卡片数据洞察生成失败: {str(card_err)}")

                # 若批量生成后某条为空，则对该条单独二次生成（不截断）
                if has_correlation and not (card_insights.get("correlation_summary") or "").strip():
                    ctx = _json.dumps(result_dict.get("strategy_conclusion") or {}, ensure_ascii=False)
                    if not ctx.strip():
                        ctx = _json.dumps(result_dict.get("correlation_results") or [], ensure_ascii=False)
                    card_insights["correlation_summary"] = await _generate_card_insight(llm, ctx, "相关性分析")
                if has_factor and not (card_insights.get("factor_summary") or "").strip():
                    ctx = _json.dumps(result_dict.get("factor_analysis") or {}, ensure_ascii=False)
                    card_insights["factor_summary"] = await _generate_card_insight(llm, ctx, "因子分析")
                if has_clustering and not (card_insights.get("clustering_summary") or "").strip():
                    ctx = _json.dumps(result_dict.get("clustering_model") or {}, ensure_ascii=False)
                    card_insights["clustering_summary"] = await _generate_card_insight(llm, ctx, "聚类分析")

            result_dict["card_insights"] = card_insights
            
            # 5. 生成综合洞察文本（基于四个分析的结果）
            if normalized_model == "all" and (result_dict.get("correlation_results") or result_dict.get("factor_analysis") or result_dict.get("clustering_model")):
                import json
                comprehensive_insight_prompt = f"""
你是专业投资分析师，请基于以下四个分析结果，为{company_name}生成深度、可操作的投资策略洞察报告。

## 分析结果数据

### 1. 相关性分析结果
{json.dumps(result_dict.get("correlation_results") or [], ensure_ascii=False, indent=2)}

### 2. 因子分析结果
{json.dumps(result_dict.get("factor_analysis") or {}, ensure_ascii=False, indent=2)}

### 3. 聚类分析结果
{json.dumps(result_dict.get("clustering_model") or {}, ensure_ascii=False, indent=2)}

### 4. 策略结论（已有）
{json.dumps(result_dict.get("strategy_conclusion") or {}, ensure_ascii=False, indent=2)}

### 5. 输入变量表（参考）
{json.dumps(result_dict.get("variable_table") or [], ensure_ascii=False, indent=2)}

## 输出要求

请生成一份**专业、深入、可操作**的投资策略洞察报告，必须包含以下内容（不含多元线性回归）：

**要求**：
1. 识别**强相关关系**（相关系数绝对值>0.7）和**中等相关关系**（0.5-0.7）
2. 解释每个相关关系的**业务含义**：
   - 为什么会有这种关联？
   - 这种关联说明了什么业务逻辑？
   - 对投资决策有什么启示？
3. 找出**反直觉的发现**（如：规模大但风险低，或增长快但质量好）
4. 识别**风险信号**（如：高相关性可能意味着集中度风险）

**示例格式**：
- "贷款余额与不良率相关系数高达0.869，说明规模大的区域不良率也偏高，可能存在区域集中度风险"
- "余额变动率与不良率变动相关系数仅0.281，说明压缩规模的产品不良率未必改善，需要关注资产质量而非单纯规模控制"

### 二、因子分析洞察

**要求**：
1. 解释**每个因子的业务含义**：
   - 因子1、因子2、因子3分别代表什么业务维度？
   - 哪些指标在这个因子上载荷高？说明什么？
2. 评估**因子解释力**：
   - 各因子解释了多少方差？
   - 累计解释方差比例是多少？
3. 识别**主要业务维度**：哪些因子最重要？反映了公司的什么特征？
4. 给出**业务优化建议**：基于因子分析，公司应该在哪些维度上重点发力？

**示例格式**：
- "因子1（规模因子）解释了45%的方差，存款余额和存款占比载荷极高(>0.99)，反映公司存款吸纳能力强"
- "因子2（风险因子）解释了32%的方差，贷款余额和不良率载荷高，反映贷款风险集中度，需要关注风险分散"

### 三、聚类分析洞察

**要求**：
1. 描述**每个聚类的特征**：
   - 每个聚类包含哪些产品/地区/业务？
   - 每个聚类的核心特征是什么？（如：低风险-低增长、中风险-高增长、高风险-大幅收缩）
2. 识别**业务策略模式**：
   - 公司正在采取什么策略？（如：压缩高风险业务、扩张低风险业务）
   - 哪些业务是重点发展对象？哪些是风险出清对象？
3. 评估**投资组合定位**：
   - 公司当前属于哪个聚类？
   - 如果要升级到更好的聚类，需要满足什么条件？
4. 给出**投资建议**：
   - 基于聚类结果，适合什么类型的投资者？
   - 短期、中期、长期的投资逻辑分别是什么？

**示例格式**：
- "聚类结果显示，公司正在主动'压缩高风险零售贷款，扩张对公企业贷款'，第三类产品（信用卡、消费贷、经营贷）是风险出清的重点"
- "公司当前定位为'中风险-高增长'组，如果要进入'低风险-稳健增长'组，需要将不良率控制在0.5%以下，同时保持ROE在12%以上"

### 四、综合投资策略建议

**要求**：
1. **整合相关性、因子、聚类三个分析的发现**，形成统一的投资逻辑
2. **识别核心投资亮点**：基于分析，公司的核心优势是什么？
3. **识别关键风险点**：需要重点关注哪些风险？
4. **给出具体投资建议**：
   - **短期（6-12个月）**：基于当前数据，短期投资逻辑是什么？
   - **中期（1-2年）**：基于业务趋势，中期投资逻辑是什么？
   - **长期（3-5年）**：基于战略定位，长期投资逻辑是什么？
5. **目标投资者画像**：适合什么风险偏好的投资者？

## 输出格式

使用Markdown格式，包含以下结构：

```markdown
# {company_name}投资策略分析报告

## 一、相关性分析洞察
[详细内容]

## 二、因子分析洞察
[详细内容]

## 三、聚类分析洞察
[详细内容]

## 四、综合投资策略建议
[详细内容]
```

**重要要求**：
- 必须基于实际分析结果，不要编造数据
- 每个洞察都要有数据支撑（引用具体的相关系数、回归系数、因子载荷等）
- 语言要专业但易懂，避免过于技术化的表述
- 给出可操作的建议，不要只是描述现象
- 如果某个分析结果不充分，明确说明局限性
"""
                try:
                    comprehensive_response = await llm.achat([
                        ChatMessage(role="system", content="你是一个专业的投资分析师，擅长整合多种分析方法生成综合洞察。"),
                        ChatMessage(role="user", content=comprehensive_insight_prompt)
                    ])
                    if hasattr(comprehensive_response, 'message'):
                        comprehensive_content = comprehensive_response.message.content if hasattr(comprehensive_response.message, 'content') else str(comprehensive_response.message)
                    else:
                        comprehensive_content = str(comprehensive_response)
                    result_dict["comprehensive_insight"] = comprehensive_content
                    logger.info("✅ 综合洞察生成成功")
                except Exception as insight_error:
                    logger.warning(f"⚠️ [generate_profit_forecast_and_valuation] 综合洞察生成失败: {str(insight_error)}")
        
        return result_dict
        
    except Exception as e:
        logger.error(f"❌ 生成投资策略（相关性分析）失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "error": f"生成投资策略（相关性分析）失败: {str(e)}",
            "company_name": company_name,
            "year": year
        }
