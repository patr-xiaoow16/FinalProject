"""
盈利预测和估值章节生成工具
"""

import logging
from typing import Dict, Any, Annotated

from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from models.report_models import ProfitForecastAndValuation

from agents.report_common import _validate_and_clean_data

logger = logging.getLogger(__name__)


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

