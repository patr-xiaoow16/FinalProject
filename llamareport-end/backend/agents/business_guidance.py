"""
业绩指引章节生成工具
"""

import json
import logging
import re
import time
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

        key_metrics_query = (
            f"{company_name} {year}年 业绩指引 关键指标 经营指标 财务指标 "
            "营业收入 净利润 净息差 不良率 资本充足率 成本收入比"
        )
        key_metrics_data = query_engine.query(key_metrics_query)

        business_segments_query = (
            f"{company_name} {year}年 业务板块指引 零售业务 对公业务 资金同业业务 "
            "业务发展计划 业务结构调整 业务转型"
        )
        business_segments_data = query_engine.query(business_segments_query)

        risk_query = (
            f"{company_name} {year}年 风险提示 不确定性 风险因素 经营风险 "
            "市场风险 信用风险 流动性风险 操作风险"
        )
        risk_data = query_engine.query(risk_query)

        strategy_query = (
            f"{company_name} {year}年 发展战略 战略方向 战略目标 战略规划 "
            "转型方向 业务转型 结构调整"
        )
        strategy_data = query_engine.query(strategy_query)

        llm = Settings.llm

        def _extract_json_block(text: str) -> Dict[str, Any]:
            if not text:
                return {}
            match = re.search(r'\{[\s\S]*\}', text)
            if not match:
                return {}
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}

        def _normalize_visualization_insights(data: Dict[str, Any]) -> Dict[str, Any]:
            if not isinstance(data, dict):
                return {}
            allowed_types = {"trend", "comparison", "distribution", "correlation", "anomaly"}
            allowed_sections = {"operating_goal", "key_metrics", "execution_path", "uncertainty"}
            normalized = {}
            for section_key, section_value in data.items():
                if section_key not in allowed_sections:
                    continue
                insights = section_value.get("insights") if isinstance(section_value, dict) else section_value
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
                        "related_items": related_items,
                    })
                if cleaned:
                    normalized[section_key] = {"insights": cleaned}
            return normalized

        # 单次调用：章节内容 + 数据提取 + 图表规划 + 洞察
        prompt = f"""
你是专业金融分析师与可视化规划助手。请基于给定材料，一次性输出完整JSON：
1) 业绩指引章节字段（business_guidance）
2) 数据提取清单（extracted_data）
3) 可视化配置（visualization_spec）
4) 可视化洞察（visualization_insights）

只输出JSON，不要解释、不要代码块。

公司：{company_name}
年份：{year}

材料：
### 基础业绩指引数据
{str(guidance_data)}

### 关键指标线索
{str(key_metrics_data)}

### 业务板块指引
{str(business_segments_data)}

### 风险提示数据
{str(risk_data)}

### 战略方向数据
{str(strategy_data)}

输出结构（严格遵守）：
{{
  "business_guidance": {{
    "guidance_period": "{year}年度",
    "expected_performance": "200-400字结论段，包含至少3个具体数值与战略基调",
    "parent_net_profit_range": null,
    "parent_net_profit_growth_range": null,
    "non_recurring_profit_range": null,
    "eps_range": null,
    "revenue_range": null,
    "key_metrics": ["至少5条，包含指标名+数值+变化+解读"],
    "business_specific_guidance": ["至少5条，包含执行动作+证据+影响"],
    "risk_warnings": ["至少3条，包含风险名称+影响对象+指标变化+概率"]
  }},
  "extracted_data": {{
    "datasets": [
      {{
        "topic": "核心指标锚点/经营目标方向/关键执行路径",
        "metric": "指标名称",
        "values": [{{"period": "期间", "value": "数值", "unit": "单位", "direction": "up/down/flat", "change": "同比/环比"}}],
        "source": "来源描述"
      }}
    ],
    "risks": [{{"risk": "风险名称", "impact": "影响对象", "probability": "高/中/低", "source": "来源描述", "related_metrics": ["相关指标"]}}],
    "execution_path": [{{"action": "执行动作", "evidence": "指标证据", "business_segment": "业务板块", "impact": "影响说明"}}],
    "strategic_direction": [{{"direction": "战略方向", "target": "目标指标", "current_value": "当前值", "target_value": "目标值"}}]
  }},
  "visualization_spec": {{
    "operating_goal": {{"chart_type": "status_card", "stage": "经营阶段", "priority": [], "key_targets": []}},
    "key_metrics": {{"chart_type": "status_bar", "items": []}},
    "execution_path": {{"chart_type": "structure_change", "items": []}},
    "uncertainty": {{"chart_type": "risk_matrix", "items": []}}
  }},
  "visualization_insights": {{
    "operating_goal": {{"insights": []}},
    "key_metrics": {{"insights": []}},
    "execution_path": {{"insights": []}},
    "uncertainty": {{"insights": []}}
  }}
}}

约束：
- 仅使用给定材料，禁止编造。
- 若缺失数据，保留空数组或null。
- visualization_insights.insight_type 仅可用: trend, comparison, distribution, correlation, anomaly。
- related_items 必须来自对应 visualization_spec 的实际条目。
"""

        merged_start = time.time()
        merged_response = await llm.achat([
            ChatMessage(role="system", content="你是金融分析与可视化规划助手，只输出JSON。"),
            ChatMessage(role="user", content=prompt),
        ])
        merged_cost = time.time() - merged_start
        logger.info(f"✅ [generate_business_guidance] 合并调用完成，耗时: {merged_cost:.2f}秒")

        merged_text = merged_response.message.content if hasattr(merged_response, "message") else str(merged_response)
        merged_payload = _extract_json_block(str(merged_text))

        if not merged_payload:
            logger.warning("⚠️ [generate_business_guidance] 合并调用未返回可解析JSON，回退文本填充")
            result_dict = BusinessGuidance(
                guidance_period=f"{year}年度",
                expected_performance=str(merged_text).strip() or "数据不足，无法生成洞察",
            ).model_dump()
            extracted_data = {}
            visualization_spec = {}
            visualization_insights = {}
        else:
            guidance_raw = merged_payload.get("business_guidance")
            if not isinstance(guidance_raw, dict):
                guidance_raw = merged_payload

            try:
                result_dict = BusinessGuidance(**guidance_raw).model_dump()
            except Exception as validation_error:
                logger.warning(f"⚠️ [generate_business_guidance] business_guidance校验失败: {validation_error}")
                result_dict = BusinessGuidance(
                    guidance_period=str(guidance_raw.get("guidance_period") or f"{year}年度"),
                    expected_performance=str(guidance_raw.get("expected_performance") or "数据不足，无法生成洞察"),
                ).model_dump()

            extracted_data = merged_payload.get("extracted_data") or {}
            visualization_spec = merged_payload.get("visualization_spec") or {}
            visualization_insights = _normalize_visualization_insights(
                merged_payload.get("visualization_insights") or {}
            )

        logger.info("✅ 业绩指引生成成功")

        result_dict["company_name"] = company_name
        result_dict["year"] = year
        if visualization_spec:
            result_dict["visualization_spec"] = visualization_spec
        if visualization_insights:
            result_dict["visualization_insights"] = visualization_insights
        if extracted_data:
            result_dict["extracted_data"] = extracted_data

        result_dict = _validate_and_clean_data(result_dict, BusinessGuidance)
        return result_dict

    except Exception as e:
        logger.error(f"❌ 生成业绩指引失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "error": f"生成业绩指引失败: {str(e)}",
            "company_name": company_name,
            "year": year,
        }
