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
        
        # 检索业绩指引相关数据（多维度检索）
        query = f"{company_name} {year}年 业绩预告 业绩指引 下一年度预期 经营计划"
        guidance_data = query_engine.query(query)

        # 补充检索核心指标锚点
        key_metrics_query = (
            f"{company_name} {year}年 业绩指引 关键指标 经营指标 财务指标 "
            "营业收入 净利润 净息差 不良率 资本充足率 成本收入比"
        )
        key_metrics_data = query_engine.query(key_metrics_query)
        
        # 补充检索业务板块指引
        business_segments_query = (
            f"{company_name} {year}年 业务板块指引 零售业务 对公业务 资金同业业务 "
            "业务发展计划 业务结构调整 业务转型"
        )
        business_segments_data = query_engine.query(business_segments_query)
        
        # 补充检索风险提示
        risk_query = (
            f"{company_name} {year}年 风险提示 不确定性 风险因素 经营风险 "
            "市场风险 信用风险 流动性风险 操作风险"
        )
        risk_data = query_engine.query(risk_query)
        
        # 补充检索战略方向
        strategy_query = (
            f"{company_name} {year}年 发展战略 战略方向 战略目标 战略规划 "
            "转型方向 业务转型 结构调整"
        )
        strategy_data = query_engine.query(strategy_query)
        
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

### 基础业绩指引数据：
{str(guidance_data)}

### 关键指标线索：
{str(key_metrics_data)}

### 业务板块指引：
{str(business_segments_data)}

### 风险提示数据：
{str(risk_data)}

### 战略方向数据：
{str(strategy_data)}

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
    {{"risk": "风险名称", "impact": "影响对象", "probability": "高/中/低", "source": "来源描述", "related_metrics": ["相关指标1", "相关指标2"]}}
  ],
  "execution_path": [
    {{"action": "执行动作", "evidence": "指标或变化证据", "business_segment": "业务板块", "impact": "影响说明"}}
  ],
  "strategic_direction": [
    {{"direction": "战略方向", "target": "目标指标", "current_value": "当前值", "target_value": "目标值"}}
  ]
}}

约束：
- 只能使用给定文本中的可核验数据
- 尽量提取更多数据，使数据集、风险、执行路径等数组尽可能丰富
- 若缺失就填空数组，不要编造
- 优先从多个数据源中提取相关信息
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
    "stage": "经营阶段/基调（如：转型期/进攻期/防守期）",
    "priority": ["风险控制", "盈利稳定", "规模增长"],
    "key_targets": [
      {{"target": "目标名称", "value": "目标值", "unit": "单位"}}
    ]
  }},
  "key_metrics": {{
    "chart_type": "status_bar",
    "items": [
      {{"name": "指标名", "value": "数值", "trend": "up/down/flat", "note": "解读", "category": "盈利能力/资产质量/成本控制/收入结构"}}
    ]
  }},
  "execution_path": {{
    "chart_type": "structure_change",
    "items": [
      {{"action": "执行动作", "evidence": "指标证据", "business_segment": "业务板块", "impact": "影响说明"}}
    ]
  }},
  "uncertainty": {{
    "chart_type": "risk_matrix",
    "items": [
      {{"risk": "风险", "impact": "影响对象", "probability": "高/中/低", "related_metrics": ["相关指标"]}}
    ]
  }}
}}

约束：
- 尽量生成丰富的可视化指令，每个板块的items数组应尽可能包含更多条目
- 如果数据不足，对应items为空数组
- 只使用提供的结构化数据，不得新增数据
- key_metrics的items应包含≥5个指标
- execution_path的items应包含≥5个执行路径
- uncertainty的items应包含≥3个风险
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
      {{"insight_type": "trend", "description": "洞察描述", "key_findings": ["要点1", "要点2"], "related_items": ["指标名1", "指标名2"]}},
      {{"insight_type": "comparison", "description": "洞察描述", "key_findings": ["要点1", "要点2"], "related_items": ["指标名3", "指标名4"]}}
    ]
  }},
  "execution_path": {{
    "insights": [
      {{"insight_type": "comparison", "description": "洞察描述", "key_findings": ["要点1", "要点2"], "related_items": ["执行动作1", "执行动作2"]}},
      {{"insight_type": "trend", "description": "洞察描述", "key_findings": ["要点1", "要点2"], "related_items": ["执行动作3", "执行动作4"]}}
    ]
  }},
  "uncertainty": {{
    "insights": [
      {{"insight_type": "anomaly", "description": "洞察描述", "key_findings": ["要点1", "要点2"], "related_items": ["风险1", "风险2"]}}
    ]
  }}
}}

约束：
- 尽量生成丰富的洞察，每个板块的insights数组应尽可能包含更多条目
- key_metrics板块应包含≥2条洞察
- execution_path板块应包含≥2条洞察
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
你是一名专业的金融分析师，负责在智能财务分析系统中生成"业绩指引洞察"与"可视化生成指令"。

你的任务是：
- 基于年报中可核验的数据与文本
- 压缩管理层已披露的经营判断与业绩指引含义
- 输出结论型洞察，并给出对应的可视化生成建议

重要说明：
- 你不是在预测未来
- 你不是在复述年报
- 你是在把管理层判断压缩为可决策信息

## 数据来源
以下数据来自{company_name} {year}年度年报中的业绩指引与经营计划部分：

### 基础业绩指引数据：
{str(guidance_data)}

### 关键指标线索：
{str(key_metrics_data)}

### 业务板块指引：
{str(business_segments_data)}

### 风险提示数据：
{str(risk_data)}

### 战略方向数据：
{str(strategy_data)}

## 任务说明
请基于年报内容，围绕以下四个固定板块生成结果：
1. 经营目标方向
2. 核心指标锚点
3. 关键执行路径
4. 不确定性与边界

## 输出要求（必须严格遵守）

### 一、经营目标方向 (expected_performance)
- 必须是一段完整的结论型文字（200-400字），包含：
  - 公司处于明确的业务结构转型期/进攻期/防守期中的哪一类
  - 核心经营目标围绕的具体数值（≥3个），每个数值都要有具体说明
  - 转型方向或战略基调的明确描述
  - 业务结构变化趋势（如：从传统零售驱动转向对公与金融市场业务并重）

### 二、核心指标锚点 (key_metrics)
- 必须是一个列表，包含≥5条核心指标洞察
- 每条洞察必须包含：
  - 指标名称
  - 具体数值（含单位）
  - 同比/环比变化（如有）
  - 简要解读（1-2句话说明该指标的意义）
- 指标应涵盖：盈利能力、资产质量、成本控制、收入结构等维度

### 三、关键执行路径 (business_specific_guidance)
- 必须是一个列表，包含≥5条执行路径洞察
- 每条洞察必须包含：
  - 执行动作/业务方向
  - 具体指标或变化证据（含数值）
  - 对整体业绩的影响说明
- 应按照业务板块分类（如：对公业务、零售业务、金融市场业务等）
- 每条路径都要有明确的量化支撑

### 四、不确定性与边界 (risk_warnings)
- 必须是一个列表，包含≥3条风险洞察
- 每条洞察必须包含：
  - 风险名称
  - 风险影响对象
  - 相关指标变化（含具体数值）
  - 风险概率评估（高/中/低）
- 应涵盖：经营风险、市场风险、资产质量风险等

### 通用要求：
- 洞察面向用户阅读，只包含判断与结论，不复述原文
- 所有洞察必须显式引用具体数值，不得使用模糊表述
- 不得输出任何示例表格或分析过程
- 若无法形成可靠结论，必须明确输出：数据不足，无法生成洞察
- 只使用给定数据与结构化数据清单，不得新增或编造数值

## 结构化数据清单（供参考）
{extracted_data}

## 字段清单（用于组织与结构化输出，不是最终展示）
以下结构仅用于组织内容，**不要输出JSON或代码块**：
{{
  "guidance_period": "业绩预告期间，如'2025年度'",
  "expected_performance": "经营目标方向的洞察（200-400字完整段落，包含转型方向、核心目标数值、业务结构变化）",
  "parent_net_profit_range": "归母净利润范围（如有，否则null）",
  "parent_net_profit_growth_range": "归母净利润增长率范围（如有，否则null）",
  "non_recurring_profit_range": "扣非净利润范围（如有，否则null）",
  "eps_range": "基本每股收益范围（如有，否则null）",
  "revenue_range": "营业收入范围（如有，否则null）",
  "key_metrics": [
    "核心指标锚点洞察1（指标名：数值，同比变化，解读）",
    "核心指标锚点洞察2（指标名：数值，同比变化，解读）",
    "...（至少5条）"
  ],
  "business_specific_guidance": [
    "关键执行路径洞察1（业务板块：执行动作，指标证据，影响说明）",
    "关键执行路径洞察2（业务板块：执行动作，指标证据，影响说明）",
    "...（至少5条，按业务板块分类）"
  ],
  "risk_warnings": [
    "不确定性与边界洞察1（风险名称，影响对象，指标变化，概率评估）",
    "不确定性与边界洞察2（风险名称，影响对象，指标变化，概率评估）",
    "...（至少3条）"
  ]
}}

### 重要提示：
- 如果某些数据缺失，请如实说明，不要编造
- "核心指标锚点"必须有具体数值支撑，优先从"补充的关键指标线索"中提炼
- "关键执行路径"应充分利用"业务板块指引"和"战略方向数据"
- "不确定性与边界"应充分利用"风险提示数据"
- 输出内容要像业务亮点一样丰富详细，每个板块都要有足够的深度和广度
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

