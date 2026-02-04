"""
投资策略（相关性分析）章节生成工具
"""

import logging
from typing import Dict, Any, Annotated, Optional

from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from models.report_models import ProfitForecastAndValuation

from agents.report_common import _validate_and_clean_data, build_correlation_results

logger = logging.getLogger(__name__)


async def generate_profit_forecast_and_valuation(
    company_name: Annotated[str, "公司名称"],
    year: Annotated[str, "年份"],
    query_engine: Any,
    model_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    生成投资策略章节（相关性分析模型）
    
    包括:
    1. 指标自动识别与抽取
    2. 输入变量表构建
    3. 相关性分析与结论输出
    
    Args:
        company_name: 公司名称
        year: 年份
        query_engine: 查询引擎
    
    Returns:
        投资策略（相关性分析）的结构化数据
    """
    try:
        logger.info(f"开始生成投资策略（相关性分析）: {company_name} {year}年")
        
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
        table_data = query_engine.query(table_query)
        report_data = query_engine.query(report_query)
        forecast_data = f"【表格】\n{str(table_data)}\n\n【年报文本】\n{str(report_data)}"
        
        # 使用 LLM 生成结构化的投资策略
        llm = Settings.llm
        normalized_model = (model_type or "all").lower()
        if normalized_model not in {"correlation", "clustering", "all"}:
            normalized_model = "all"

        prompt = f"""
作为资深投资分析师，请基于以下数据，为{company_name}生成“投资策略-相关性分析模型”。

## 数据来源
以下数据来自年报披露与相关指标说明：

{str(forecast_data)}

## 分析要求
请只完成“指标抽取与结构化”，不要计算相关性，也不要写投资策略结论：

### 1. 指标自动识别与抽取（严格口径）
仅允许识别并抽取以下指标（名称必须与下列一致，不要扩展或改写）：
- 收益类（因变量）：短期收益（股息驱动）、长期收益（盈利驱动）
- 盈利类（自变量）：净息差（NIM）、非息收入增速
- 风险类（自变量）：还原后不良贷款率、核心一级资本充足率、拨备覆盖率
- 业务类（自变量）：零售贷款增速、对公新兴行业贷款增速
- 估值类（自变量）：市净率（PB）、分红率
- 风险敞口类（自变量）：房地产敞口不良率

输出每个指标的分类、变量角色（因变量/自变量）、取值、单位、期间和来源片段。

### 2. 输入变量表
- 将指标整理为“输入变量表”（变量类型、具体指标、取值、期间、单位）
- 仅使用本年报中的数据；若表格内存在多个年份列，请一并抽取并标注period

### 3. 相关性与结论（不要生成）
- "correlation_results"必须输出空数组[]
- "strategy_conclusion"中的字段保持为空字符串或空数组

### 4. 模型选择约束（由后端控制）
- model_type=correlation：只做相关性分析，不生成聚类模型
- model_type=clustering：只做聚类模型，不生成相关性结果
- model_type=all：相关性与聚类模型均可生成

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
- 直接输出上述JSON结构，不要有任何其他内容
"""

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
                # 处理Response对象，message.content可能是字符串
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
                    ChatMessage(role="system", content="你是一个专业的投资分析师,擅长相关性分析与投资策略。你必须严格按照用户要求的JSON格式输出，只输出JSON，不要有任何其他文字。"),
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
                    if 'investment_strategy' in parsed_data or 'profit_forecast_and_valuation' in parsed_data:
                        parsed_data = parsed_data.get('investment_strategy') or parsed_data.get('profit_forecast_and_valuation') or parsed_data
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

        logger.info(f"✅ 投资策略（相关性分析）生成成功")
        
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
        if isinstance(result_dict, dict):
            data_sufficiency = result_dict.get("data_sufficiency")
            if isinstance(data_sufficiency, dict) and not isinstance(data_sufficiency.get("is_sufficient"), bool):
                data_sufficiency["is_sufficient"] = False

        # 使用代码计算相关性（优先于LLM填充）
        if isinstance(result_dict, dict):
            if normalized_model in {"correlation", "all"}:
                correlation_results = result_dict.get("correlation_results") or []
                data_sufficiency = result_dict.get("data_sufficiency")
                if not correlation_results:
                    computed_results, computed_sufficiency = build_correlation_results(
                        result_dict.get("indicator_extraction") or [],
                        result_dict.get("variable_table") or [],
                        year
                    )
                    result_dict["correlation_results"] = computed_results
                    result_dict["data_sufficiency"] = data_sufficiency or computed_sufficiency
                elif not data_sufficiency:
                    _, computed_sufficiency = build_correlation_results(
                        result_dict.get("indicator_extraction") or [],
                        result_dict.get("variable_table") or [],
                        year
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
你是专业投资分析师，请仅基于给定的相关性结果与数据充分性说明，生成投资策略结论。
不得新增或编造任何数值，不得虚构相关系数。

### 相关性结果
{json.dumps(result_dict.get("correlation_results") or [], ensure_ascii=False)}

### 数据充分性
{json.dumps(result_dict.get("data_sufficiency") or {}, ensure_ascii=False)}

### 输入变量表（供命名参考）
{json.dumps(result_dict.get("variable_table") or [], ensure_ascii=False)}

### 输出要求
必须输出JSON且只输出JSON，结构如下：
{{
  "strategy_conclusion": {{
    "short_term": "短期配置结论",
    "long_term": "长期配置结论",
    "risk_control": "风险管控结论",
    "key_signals": ["关键信号1", "关键信号2"]
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

            # 生成聚类分析模型（从表格+年报文本自动填充）
            if normalized_model in {"clustering", "all"} and not result_dict.get("clustering_model"):
                import json
                clustering_prompt = f"""
你是专业投研分析师，请基于以下数据生成“聚类分析模型（客群-标的适配分组）”。
仅使用提供的数据，不要编造；缺失处用null或空字符串。

### 数据来源（表格优先，其次年报文本）
{str(forecast_data)}

### 必须包含的变量设计（维度与指标名称必须一致）
- 估值维度：市净率（PB）
- 盈利维度：加权平均ROE
- 风险维度：还原后不良贷款率
- 增长维度：对公贷款增速
- 防御维度：股息率

### 参考行业对标对象（如有披露）
招行、兴业、股份行均值（2024年）

### 聚类结果（固定K=3，按区间规则归类）
组别1：高股息低估值防御组
组别2：稳健增长组
组别3：高增长高弹性组

### 输出要求
必须输出JSON且只输出JSON，结构如下：
{{
  "clustering_model": {{
    "method": "K-means",
    "k": 3,
    "variable_table": [
      {{
        "dimension": "估值维度",
        "metric": "市净率（PB）",
        "company_value": "0.55",
        "industry_benchmark": "招行0.82、兴业0.61、股份行均值0.73"
      }}
    ],
    "group_results": [
      {{
        "group_name": "组别1：高股息低估值防御组",
        "feature_profile": "PB<0.6、股息率>5%、ROE10%-11%、还原后不良率1.7%-1.8%",
        "company_assignment": "核心标的/边缘标的/暂不归属",
        "investor_profile": "收益目标5%-8%、风险容忍度低、流动性需求中",
        "time_risk_bucket": "短期（6-12个月）-低风险"
      }}
    ],
    "conclusion": {{
      "current_position": "当前分组结论",
      "upgrade_conditions": "进入稳健增长组条件",
      "high_growth_conditions": "进入高增长高弹性组条件"
    }}
  }}
}}
"""
                try:
                    clustering_response = await llm.achat([
                        ChatMessage(role="system", content="你是专业投研分析师，必须严格输出JSON。"),
                        ChatMessage(role="user", content=clustering_prompt)
                    ])
                    if hasattr(clustering_response, 'message'):
                        clustering_content = clustering_response.message.content if hasattr(clustering_response.message, 'content') else str(clustering_response.message)
                    else:
                        clustering_content = str(clustering_response)
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', clustering_content)
                    if json_match:
                        parsed = json.loads(json_match.group(0))
                        clustering_model = parsed.get("clustering_model") if isinstance(parsed, dict) else None
                        if isinstance(clustering_model, dict):
                            result_dict["clustering_model"] = clustering_model
                except Exception as clustering_error:
                    logger.warning(f"⚠️ [generate_profit_forecast_and_valuation] 聚类模型生成失败: {str(clustering_error)}")
        
        try:
            import json
            logger.info("📦 投资策略JSON结果:\n%s", json.dumps(result_dict, ensure_ascii=False, indent=2))
        except Exception as log_error:
            logger.warning("⚠️ 投资策略JSON日志输出失败: %s", str(log_error))

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

