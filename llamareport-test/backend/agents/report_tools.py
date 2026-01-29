"""
年报分析 Agent 工具函数
每个工具负责生成报告的一个章节
"""

import logging
from typing import Dict, Any, List, Optional, Annotated
from llama_index.core.tools import FunctionTool, QueryEngineTool
from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from models.report_models import (
    FinancialReview,
    BusinessGuidance,
    BusinessHighlights,
    ProfitForecastAndValuation,
    BusinessHighlight,
    ConsensusForecas,
    ValuationAnalysis,
    FinancialStatementTable,
    FinancialStatementTables
)
from agents.visualization_agent import generate_visualization_for_query

logger = logging.getLogger(__name__)


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


async def generate_profit_forecast_and_valuation(
    company_name: Annotated[str, "公司名称"],
    year: Annotated[str, "年份"],
    query_engine: Any
) -> Dict[str, Any]:
    """
    生成盈利预测和估值章节
    
    包括:
    1. 一致预测
    2. 机构预测
    3. 估值分析
    
    Args:
        company_name: 公司名称
        year: 年份
        query_engine: 查询引擎
    
    Returns:
        盈利预测和估值的结构化数据
    """
    try:
        logger.info(f"开始生成盈利预测和估值: {company_name} {year}年")
        
        # 检索预测和估值数据
        query = f"{company_name} 盈利预测 机构评级 目标价 估值分析 PE PB ROE"
        forecast_data = query_engine.query(query)
        
        # 使用 LLM 生成结构化的盈利预测和估值
        llm = Settings.llm

        prompt = f"""
作为资深投资分析师，请基于以下数据，生成{company_name}的专业盈利预测和估值分析。

## 数据来源
以下数据来自市场一致预测、机构评级、估值分析等：

{str(forecast_data)}

## 分析要求
请生成结构化的盈利预测和估值分析，要求如下：

### 1. 一致预测
- **市场整体评级**：综合市场对公司的评级（买入/增持/中性/减持/卖出）
- **目标价**：市场一致目标价及当前价格对比
- **财务指标预测**：未来1-3年的收入、利润、EPS等关键指标预测
- **增长率预测**：各项指标的预期增长率

### 2. 一致预期变化
- 对比近期一致预期的变化趋势
- 分析预期上调或下调的原因
- 评估预期变化的合理性

### 3. 具体机构预测
- 列出主要机构的预测和评级
- 对比不同机构的观点差异
- 识别市场共识和分歧点

### 4. 估值分析
- **估值方法**：使用的估值方法（PE、PB、DCF、PEG等）
- **当前估值**：基于各种方法的估值水平
- **估值对比**：与同行业、历史估值、市场平均的对比
- **估值结论**：评估当前估值是否合理，是否具有投资价值

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
  "consensus_forecast": {{
    "market_rating": "市场整体评级（如'买入'、'增持'、'中性'）",
    "target_price": "一致目标价（如有，否则null）",
    "upside_potential": "上涨空间（如有，否则null）",
    "revenue_forecast": {{"year": "年份", "value": "预测值", "growth_rate": "增长率"}},
    "profit_forecast": {{"year": "年份", "value": "预测值", "growth_rate": "增长率"}},
    "eps_forecast": {{"year": "年份", "value": "预测值", "growth_rate": "增长率"}}
  }},
  "forecast_changes": {{
    "recent_changes": "近期一致预期变化描述",
    "change_reasons": "预期变化原因分析",
    "change_trend": "变化趋势（上调/下调/持平）"
  }},
  "institution_forecasts": [
    {{
      "institution_name": "机构名称",
      "rating": "评级",
      "target_price": "目标价",
      "forecast_period": "预测期间"
    }},
    ...
  ],
  "valuation_analysis": {{
    "valuation_methods": ["PE", "PB", "DCF", ...],
    "current_valuation": "当前估值水平描述",
    "valuation_comparison": "估值对比分析",
    "valuation_conclusion": "估值结论"
  }}
}}

### 重要提示：
- 如果某些数据缺失，使用null或空数组[]
- 所有字段都必须存在，不能省略
- 直接输出上述JSON结构，不要有任何其他内容
"""

        # 使用结构化输出 - 添加异常处理和性能监控
        response = None
        import time
        structured_llm_start = time.time()
        try:
            sllm = llm.as_structured_llm(ProfitForecastAndValuation)
            raw_response = await sllm.achat([
                ChatMessage(role="system", content="你是一个专业的投资分析师,擅长盈利预测和估值分析。你必须严格按照用户要求的JSON格式输出，只输出JSON，不要有任何其他文字。"),
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
                    if 'profit_forecast' in parsed_data or 'valuation' in parsed_data:
                        parsed_data = parsed_data.get('profit_forecast') or parsed_data.get('valuation') or parsed_data
                    response = ProfitForecastAndValuation(**parsed_data) if isinstance(parsed_data, dict) and 'consensus_forecast' in parsed_data else parsed_data
                else:
                    raise ValueError("无法从字符串响应提取JSON")
            elif isinstance(raw_response, ProfitForecastAndValuation):
                response = raw_response
            elif hasattr(raw_response, 'message') and hasattr(raw_response.message, 'content'):
                # 处理Response对象，message.content可能是字符串
                content = raw_response.message.content
                if isinstance(content, str):
                    logger.warning(f"⚠️ [generate_profit_forecast_and_valuation] 响应message.content是字符串，尝试解析JSON")
                    import json
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', content)
                    if json_match:
                        parsed_data = json.loads(json_match.group(0))
                        if 'profit_forecast' in parsed_data or 'valuation' in parsed_data:
                            parsed_data = parsed_data.get('profit_forecast') or parsed_data.get('valuation') or parsed_data
                        response = ProfitForecastAndValuation(**parsed_data) if isinstance(parsed_data, dict) and 'consensus_forecast' in parsed_data else parsed_data
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
            
            # 更详细的错误信息
            if "model_dump_json" in error_msg or "AttributeError" in error_type:
                logger.warning(f"⚠️ [generate_profit_forecast_and_valuation] 结构化LLM返回了字符串而非Pydantic模型（耗时: {structured_llm_time:.2f}秒）")
                logger.warning(f"[generate_profit_forecast_and_valuation] 错误类型: {error_type}, 错误信息: {error_msg}")
                logger.info(f"[generate_profit_forecast_and_valuation] 这是LlamaIndex的已知问题，将尝试从字符串解析JSON")
            else:
                logger.warning(f"⚠️ [generate_profit_forecast_and_valuation] 结构化输出失败（{error_type}，耗时: {structured_llm_time:.2f}秒）: {error_msg}")
            
            logger.info(f"[generate_profit_forecast_and_valuation] 尝试使用普通LLM输出并手动解析JSON")
            # 回退到普通LLM输出
            try:
                normal_response = await llm.achat([
                    ChatMessage(role="system", content="你是一个专业的投资分析师,擅长盈利预测和估值分析。你必须严格按照用户要求的JSON格式输出，只输出JSON，不要有任何其他文字。"),
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
                    if 'profit_forecast' in parsed_data or 'valuation' in parsed_data:
                        parsed_data = parsed_data.get('profit_forecast') or parsed_data.get('valuation') or parsed_data
                    elif len(parsed_data) == 1:
                        parsed_data = list(parsed_data.values())[0]
                    
                    try:
                        response = ProfitForecastAndValuation(**parsed_data)
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

        logger.info(f"✅ 盈利预测和估值生成成功")
        
        # 处理响应 - 确保返回字典格式
        result_dict = None
        
        # 如果response是字典且包含error，直接返回
        if isinstance(response, dict) and 'error' in response:
            result_dict = response
        # 首先检查是否是Pydantic模型
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
        
        # 数据验证和清理
        result_dict = _validate_and_clean_data(result_dict, ProfitForecastAndValuation)
        
        return result_dict
        
    except Exception as e:
        logger.error(f"❌ 生成盈利预测和估值失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "error": f"生成盈利预测和估值失败: {str(e)}",
            "company_name": company_name,
            "year": year
        }

