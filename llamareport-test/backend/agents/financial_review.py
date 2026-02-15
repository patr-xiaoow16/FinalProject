"""
财务点评章节生成工具
"""

import logging
from typing import Dict, Any, List, Optional, Annotated

from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from models.report_models import (
    FinancialReview,
    FinancialStatementTable,
    FinancialStatementTables
)

from agents.report_common import _validate_and_clean_data, retrieve_financial_data

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
作为资深财务分析师，请基于以下财务数据，生成{company_name} {year}年度的财务点评总结，并构建可视化表格视图。内容要充实，但必须严格按资产负债表 / 利润表 / 现金流量表 / 综合判断拆分。

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

### 1. 财务点评总结（内容丰富）
你是一名专业的财务分析师，请基于我提供的资产负债表、利润表和现金流量表数据，
分别对三张表进行分段分析，并给出一个综合三表的总体判断。

分析要求如下：

一、资产负债表分析（分段）
请从以下三个角度综合判断：
1. 资产结构：公司的资产主要由什么构成？（如现金、存货、固定资产、金融资产等）
2. 偿债风险：结合资产负债率，判断杠杆水平是否偏高或可控
3. 实力基础：所有者权益规模及变化趋势，反映公司的“家底”是否稳健

要求：
- 用分段方式输出，至少3-5条要点 + 1段总结
- 以“结构 + 风险 + 实力”为主线
- 必须引用关键指标与数值（指标名+数值/同比）
- 不引入未给出的指标，不编造数据
- 不要有字数限制，内容尽量充分

输出格式：
资产负债表：
- 要点1……
- 要点2……
- 要点3……
总结：XXXXXX

二、利润表分析（分段）
请从以下三个角度综合判断：
1. 趋势：收入和净利润是增长还是下滑，变化是否一致
2. 利润质量：利润主要来自主营业务还是依赖非经常性项目（如资产处置、投资收益）
3. 成本结构：毛利水平、费用控制情况

要求：
- 用分段方式输出，至少3-5条要点 + 1段总结
- 突出经营质量与结构变化
- 必须引用关键指标与数值（指标名+数值/同比）
- 不引入未给出的指标，不编造数据
- 不要有字数限制，内容尽量充分

输出格式：
利润表：
- 要点1……
- 要点2……
- 要点3……
总结：XXXXXX

三、现金流量表分析（分段）
请从以下三个角度综合判断：
1. 经营现金流状况：是否稳定、是否足以覆盖投资或分红
2. 投资支出情况：是否扩张，投资现金流是否为负
3. 筹资活动特征：是否通过借款或股权融资弥补现金流

要求：
- 用分段方式输出，至少3-5条要点 + 1段总结
- 着眼“现金创造能力 + 资金使用方向”
- 必须引用关键指标与数值（指标名+数值/同比）
- 不引入未给出的指标，不编造数据
- 不要有字数限制，内容尽量充分

输出格式：
现金流量表：
- 要点1……
- 要点2……
- 要点3……
总结：XXXXXX

四、综合判断（分段）
请综合三张报表给出企业整体财务健康状况的判断

要求：
- 用分段方式输出，至少3-5条要点 + 1段总结
- 强调财务稳健性、成长性或风险点
- 必须引用关键指标与数值（指标名+数值/同比）
- 不要出现“建议、应当”等措辞
- 不要有字数限制，内容尽量充分

输出格式：
综合判断：
- 要点1……
- 要点2……
- 要点3……
总结：XXXXXX

### 2. 财务报表可视化表格
请输出三张财务报表的可视化表格数据，用于前端展示。

财务报表表格要求如下：

1. 资产负债表（资产结构）
需要展示以下指标：
- 资产总额
- 发放贷款及垫款
- 个人贷款
- 企业贷款
- 投资类金融资产
- 现金及存放央行款项
- 存放同业款项

2. 资产负债表（负债结构）
需要展示以下指标：
- 负债总额
- 吸收存款
- 个人存款
- 企业存款
- 向央行借款
- 同业负债
- 已发行债务证券
- 卖出回购金融资产

3. 利润表（营业收入结构）
需要展示以下指标：
- 营业收入合计
- 利息净收入
- 非利息净收入
- 手续费及佣金净收入
- 其他非利息净收入
- 投资收益
- 公允价值变动损益

4. 利润表（营业支出结构）
需要展示以下指标：
- 营业支出合计
- 业务及管理费
- 信用及其他资产减值损失
- 税金及附加

5. 现金流量表
需要展示以下指标：
- 经营活动现金流
- 投资活动现金流
- 筹资活动现金流
- 现金净变动额

表格输出结构参考：
{{
    "title": "表格标题",
    "headers": ["指标", "2023", "2022", "同比变动"],
    "rows": [
        ["资产总额", "1000亿元", "900亿元", "+11.1%"],
        ["发放贷款及垫款", "600亿元", "550亿元", "+9.1%"],
        ...
    ],
    "insight": "对该表格的简要分析或洞察"
}}

请严格输出JSON格式，结构如下：
{{
  "summary": {{
    "balance_sheet": "资产负债表总结",
    "income_statement": "利润表总结",
    "cash_flow": "现金流量表总结",
    "overall": "综合判断"
  }},
  "visualization_tables": {{
    "balance_sheet_assets": {{...}},
    "balance_sheet_liabilities": {{...}},
    "income_statement_revenue": {{...}},
    "income_statement_expense": {{...}},
    "cash_flow": {{...}}
  }}
}}
"""

        response = None
        structured_llm_start = time.time()
        try:
            sllm = llm.as_structured_llm(FinancialReview)
            raw_response = await sllm.achat([
                ChatMessage(role="system", content="你是一个专业的财务分析师,擅长分析年报数据。你必须严格按照用户要求的JSON格式输出，只输出JSON，不要有任何其他文字。"),
                ChatMessage(role="user", content=prompt)
            ])
            
            # 检查响应类型 - 处理字符串响应
            if isinstance(raw_response, str):
                logger.warning(f"⚠️ [generate_financial_review] 结构化LLM返回字符串，尝试解析JSON")
                import json
                import re
                json_match = re.search(r'\{[\s\S]*\}', raw_response)
                if json_match:
                    parsed_data = json.loads(json_match.group(0))
                    if 'financial_review' in parsed_data:
                        parsed_data = parsed_data['financial_review']
                    response = FinancialReview(**parsed_data) if isinstance(parsed_data, dict) and 'summary' in parsed_data else parsed_data
                else:
                    raise ValueError("无法从字符串响应提取JSON")
            elif isinstance(raw_response, FinancialReview):
                response = raw_response
            elif hasattr(raw_response, 'message') and hasattr(raw_response.message, 'content'):
                # 处理Response对象，message.content可能是字符串
                content = raw_response.message.content
                if isinstance(content, str):
                    logger.warning(f"⚠️ [generate_financial_review] 响应message.content是字符串，尝试解析JSON")
                    import json
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', content)
                    if json_match:
                        parsed_data = json.loads(json_match.group(0))
                        if 'financial_review' in parsed_data:
                            parsed_data = parsed_data['financial_review']
                        response = FinancialReview(**parsed_data) if isinstance(parsed_data, dict) and 'summary' in parsed_data else parsed_data
                    else:
                        raise ValueError("无法从message.content提取JSON")
                else:
                    response = content
            elif hasattr(raw_response, 'raw'):
                # 处理raw属性的情况
                logger.info(f"🔍 [generate_financial_review] 发现raw属性，类型: {type(raw_response.raw).__name__}")
                raw_data = raw_response.raw
                if isinstance(raw_data, FinancialReview):
                    response = raw_data
                    logger.info(f"✅ [generate_financial_review] 从raw属性获取Pydantic模型成功")
                elif hasattr(raw_data, 'model_dump'):
                    try:
                        raw_dict = raw_data.model_dump()
                        response = FinancialReview(**raw_dict)
                        logger.info(f"✅ [generate_financial_review] 从raw.model_dump()重建模型成功")
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

