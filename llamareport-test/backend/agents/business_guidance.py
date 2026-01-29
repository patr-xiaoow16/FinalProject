"""
业绩指引章节生成工具
"""

import logging
from typing import Dict, Any, Annotated

from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from models.report_models import BusinessGuidance

from agents.report_common import _validate_and_clean_data

logger = logging.getLogger(__name__)


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

        prompt = f"""
作为资深财务分析师，请基于以下数据，生成{company_name} {year}年度的专业业绩指引分析。

## 数据来源
以下数据来自{company_name} {year}年度年报中的业绩指引和经营计划部分：

{str(guidance_data)}

补充的关键指标线索（如有）：
{str(key_metrics_data)}

## 分析要求（思考流程不变）
请先按“字段清单”组织信息，覆盖要点并避免遗漏。
然后按“输出格式”生成最终内容。

## 结构化参考（用于组织内容，不是输出格式要求）
以下JSON结构仅作为字段清单，帮助你组织思考。
不要输出JSON或代码块。

### 字段清单（示例结构）：
{{
  "guidance_period": "业绩预告期间，如'2025年度'",
  "expected_performance": "预计的经营业绩描述",
  "parent_net_profit_range": "归母净利润范围（如有，否则null）",
  "parent_net_profit_growth_range": "归母净利润增长率范围（如有，否则null）",
  "non_recurring_profit_range": "扣非净利润范围（如有，否则null）",
  "eps_range": "基本每股收益范围（如有，否则null）",
  "revenue_range": "营业收入范围（如有，否则null）",
  "key_metrics": ["指标A：数值（含单位/口径）", "指标B：数值（含同比/增速）"],
  "business_specific_guidance": ["业务1指引", "业务2指引"],
  "risk_warnings": ["风险1", "风险2"]
}}

### 重要提示：
- 如果某些数据缺失，请如实说明，不要编造
- 关注可读性与专业性，避免空泛表述
- “核心指标锚点”必须有具体数值支撑，优先从“补充的关键指标线索”中提炼

## 输出格式（最终输出，必须遵守）
必须严格按①~④四个方面输出，每个方面单独成点（一个编号=一个要点段落）。

① 经营目标方向（What）
接下来一段时间，公司要“优先做好什么”？
最低要求（至少说清楚一个）：
- 追求增长 vs 稳定
- 盈利优先 vs 规模优先
- 修复 vs 转型
📌 典型表述：
- “坚持稳健经营”
- “优先保证资产质量”
- “以盈利能力改善为核心”

② 核心指标锚点（Watch）
希望“盯哪些指标”？

③ 关键执行路径（How）
- 结构调整
- 成本控制
- 风控加强
- 资源倾斜方向

④ 不确定性与边界
这一块99% 藏在风险提示里：
- 外部环境
- 政策变化
- 行业周期
- 客户行为
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

