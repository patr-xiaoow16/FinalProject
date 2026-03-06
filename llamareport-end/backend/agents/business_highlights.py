"""
业务亮点章节生成工具
"""

import logging
from typing import Dict, Any, Annotated, Optional, List

import json
import os
import re
import asyncio
import time
from pathlib import Path

from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from models.report_models import BusinessHighlights
from models.business_schema import (
    IndustryClassificationResult,
    SegmentSelectionResult,
    ExtractedSegmentMetrics,
    BusinessPerformanceReport
)

from agents.report_common import _validate_and_clean_data
from agents.business_schema_templates import get_business_schema, BUSINESS_SCHEMA_TEMPLATES

logger = logging.getLogger(__name__)

MAX_TOTAL_SECONDS = int(os.getenv("BH_MAX_TOTAL_SECONDS", "110"))
QUERY_TIMEOUT_SECONDS = int(os.getenv("BH_QUERY_TIMEOUT_SECONDS", "14"))
LLM_TIMEOUT_SECONDS = int(os.getenv("BH_LLM_TIMEOUT_SECONDS", "22"))
ENABLE_RULE_ENRICH = os.getenv("BH_ENABLE_RULE_ENRICH", "0") == "1"
RULE_ENRICH_MAX_QUERIES = int(os.getenv("BH_RULE_ENRICH_MAX_QUERIES", "4"))
INDUSTRY_LLM_MIN_TEXT_LEN = int(os.getenv("BH_INDUSTRY_LLM_MIN_TEXT_LEN", "180"))
METRIC_RULES_PATH = Path(__file__).resolve().parent / "business_metric_rules.json"


def _load_metric_rules() -> Dict[str, Any]:
    try:
        with METRIC_RULES_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"⚠️ 指标规则加载失败: {e}")
        return {}


METRIC_RULES = _load_metric_rules()


def _get_metric_rule(industry: str, segment_id: str) -> Dict[str, Any]:
    direct = (
        METRIC_RULES.get(industry, {})
        .get(segment_id, {})
    )
    if direct:
        return direct
    for industry_key, segments in METRIC_RULES.items():
        if segment_id in segments:
            logger.info(f"🔁 [business_highlights] 指标规则行业回退: {industry} -> {industry_key}")
            return segments.get(segment_id, {})
    return {}


def _normalize_metric_name(name: str) -> str:
    return name.replace(" ", "").replace("（", "(").replace("）", ")")


def _build_metric_aliases(metric_name: str) -> List[str]:
    if not metric_name:
        return []
    aliases = set()
    aliases.add(metric_name)
    replacements = {
        "余额": ["规模", "余额"],
        "收入": ["收入", "营收"],
        "净利润": ["净利润", "利润", "净利"],
        "不良率": ["不良率", "不良贷款率"],
        "减值损失": ["减值损失", "信用减值损失"],
        "AUM": ["AUM", "管理资产规模"],
        "客户数": ["客户数", "客户数量"],
    }
    for key, candidates in replacements.items():
        if key in metric_name:
            for candidate in candidates:
                aliases.add(metric_name.replace(key, candidate))
    return [a for a in aliases if a]


def _infer_industry_from_company_name(company_name: str) -> Optional[str]:
    if not company_name:
        return None
    if "银行" in company_name:
        return "banking"
    if "保险" in company_name or "人寿" in company_name:
        return "insurance"
    if "证券" in company_name:
        return "securities"
    if "互联网" in company_name or "科技" in company_name:
        return "internet_platform"
    if "制造" in company_name or "工业" in company_name:
        return "manufacturing"
    return None


def _infer_industry_from_overview_text(overview_text: str) -> Optional[str]:
    text = str(overview_text or "")
    if not text:
        return None
    keyword_map = {
        "banking": ["净息差", "不良贷款率", "拨备覆盖率", "资本充足率", "对公贷款", "零售银行"],
        "insurance": ["原保费", "赔付", "退保", "寿险", "财险", "综合成本率"],
        "securities": ["经纪业务", "投行业务", "资管计划", "两融", "自营"],
        "internet_platform": ["gmv", "mau", "平台商家", "广告变现", "在线营销"],
        "manufacturing": ["产能", "产量", "销量", "订单", "生产线", "毛利率"],
    }
    text_l = text.lower()
    best_industry = None
    best_score = 0
    for industry, keywords in keyword_map.items():
        score = sum(1 for kw in keywords if kw.lower() in text_l)
        if score > best_score:
            best_score = score
            best_industry = industry
    if best_score >= 2:
        return best_industry
    return None


def _map_dimension_to_category(dimension: str) -> str:
    dim = (dimension or "").lower()
    if "profit" in dim or "盈利" in dim:
        return "profitability"
    if "risk" in dim or "风险" in dim:
        return "risk"
    if "efficiency" in dim or "capability" in dim or "效率" in dim or "能力" in dim:
        return "efficiency"
    return "scale"


def _extract_numeric_candidates(text: str) -> List[str]:
    if not text:
        return []
    pattern = r"(\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?(?:万亿|万|亿|元|%|亿元|万元|bp|bps)?"
    return [m.group(0) for m in re.finditer(pattern, text)]


def _extract_year_value(text: str, target_year: str, exclude_values: Optional[set] = None) -> Optional[str]:
    if not text:
        return None
    exclude_values = exclude_values or set()
    pattern = rf"{re.escape(target_year)}[^\d]{{0,12}}([\d,\.]+(?:万亿|万|亿|元|%|亿元|万元|bp|bps)?)"
    matches = list(re.finditer(pattern, text))
    for match in matches:
        value = match.group(1)
        if value and value not in exclude_values and value != target_year:
            return value
    return None


def _extract_yoy_change(text: str) -> Optional[str]:
    if not text:
        return None
    pattern = r"(同比|增长|下降|减少|增速)[^\d]{0,8}([\d,\.]+%)"
    match = re.search(pattern, text)
    if match:
        return match.group(2)
    return None


async def _enrich_metrics_with_rules(
    metrics_mapping: Dict[str, Any],
    industry: str,
    company_name: str,
    year: str,
    query_engine: Any,
    time_remaining_func
) -> Dict[str, Any]:
    if not metrics_mapping.get("segments"):
        return metrics_mapping

    max_queries = max(0, RULE_ENRICH_MAX_QUERIES)
    query_count = 0

    for segment in metrics_mapping.get("segments", []):
        segment_id = segment.get("segment_id")
        segment_name = segment.get("segment_name", segment_id)
        if not segment_id:
            continue
        rule = _get_metric_rule(industry, segment_id) or {}
        required = rule.get("required", [])
        optional = rule.get("optional", [])
        metrics_to_fetch = required + optional
        if metrics_to_fetch:
            metric_names = [m.get("name") for m in metrics_to_fetch if m.get("name")]
            logger.info(f"🔎 [business_highlights] 业务板块 {segment_id} 指标检索列表: {metric_names}")

        mapped_metrics = segment.setdefault("mapped_metrics", {})

        existing = {}
        for category, items in mapped_metrics.items():
            if not isinstance(items, list):
                continue
            for item in items:
                metric_name = item.get("metric")
                if metric_name:
                    existing[_normalize_metric_name(metric_name)] = item

        for metric in metrics_to_fetch:
            if query_count >= max_queries or time_remaining_func() <= 15:
                return metrics_mapping
            metric_name = metric.get("name")
            if not metric_name:
                continue
            if _normalize_metric_name(metric_name) in existing:
                continue

            aliases = _build_metric_aliases(metric_name)
            query_terms = " ".join(aliases[:3]) if aliases else metric_name
            query = (
                f"{company_name} {year}年 {segment_name} {query_terms} "
                f"上年 同比 变动 数值"
            )
            try:
                raw_text = await _run_query_with_timeout(
                    query_engine,
                    query,
                    QUERY_TIMEOUT_SECONDS
                )
            except Exception as e:
                logger.warning(f"⚠️ 指标检索失败: {segment_id}-{metric_name}: {e}")
                raw_text = ""

            prev_year = str(int(year) - 1) if year.isdigit() else ""
            exclude = {year, prev_year} if prev_year else {year}
            current_val = _extract_year_value(str(raw_text), year, exclude) or None
            prev_val = _extract_year_value(str(raw_text), prev_year, exclude) if prev_year else None
            yoy_change = _extract_yoy_change(str(raw_text))
            if not current_val:
                candidates = _extract_numeric_candidates(str(raw_text))
                for candidate in candidates:
                    if candidate not in exclude:
                        current_val = candidate
                        break
            logger.info(
                f"📌 [business_highlights] {segment_id} - {metric_name}: "
                f"{year}={current_val or '/'} {prev_year or '上年'}={prev_val or '/'} 同比={yoy_change or '/'}"
            )

            category = _map_dimension_to_category(metric.get("dimension"))
            mapped_metrics.setdefault(category, [])
            mapped_metrics[category].append({
                "metric": metric_name,
                "current_year": current_val or "/",
                "previous_year": prev_val or "/",
                "yoy_change": yoy_change or "/",
                "evidence": str(raw_text)[:500]
            })
            query_count += 1

    return metrics_mapping


async def _run_with_timeout(coro, timeout: int, fallback, step_name: str):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"⚠️ [generate_business_highlights] {step_name} 超时({timeout}s)，使用降级结果")
        return fallback


async def _run_query_with_timeout(query_engine: Any, query: str, timeout: int) -> str:
    loop = asyncio.get_running_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(None, query_engine.query, query),
        timeout=timeout
    )


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    json_match = re.search(r'\{[\s\S]*\}', text)
    if not json_match:
        return None
    try:
        return json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return None


def _extract_llm_content(raw_response: Any) -> str:
    if isinstance(raw_response, str):
        return raw_response
    if hasattr(raw_response, 'message') and hasattr(raw_response.message, 'content'):
        return str(raw_response.message.content)
    if hasattr(raw_response, 'content'):
        return str(raw_response.content)
    return str(raw_response)


def _build_segment_rules(schema: Dict[str, Any], industry: str) -> Dict[str, Any]:
    segment_rules = {}
    for segment in schema.get("segments", []):
        segment_id = segment.get("segment_id")
        if not segment_id:
            continue
        rule = _get_metric_rule(industry, segment_id)
        if rule:
            segment_rules[segment_id] = rule
    return segment_rules


async def _select_segments_and_map_metrics(
    llm: Any,
    industry: str,
    schema: Dict[str, Any],
    business_data: str,
    overview_data: str,
    segment_rules: Dict[str, Any]
) -> Dict[str, Any]:
    prompt = f"""
你是企业年报“业务结构识别 + 指标映射”模块，必须一次输出完整JSON。

输入：
industry = {industry}
segments template =
{json.dumps(schema, ensure_ascii=False)}

annual report business snippets =
<<<
{business_data}
>>>

annual report overview snippets =
<<<
{overview_data}
>>>

metric rules =
{json.dumps(segment_rules, ensure_ascii=False)}

请严格输出JSON：
{{
  "industry": "{industry}",
  "selected_segments": ["segment_id1","segment_id2"],
  "reasoning": ["..."],
  "evidence": ["..."],
  "segments": [
    {{
      "segment_id": "retail_banking",
      "segment_name": "零售银行业务",
      "mapped_metrics": {{
        "scale": [{{"metric": "指标名", "current_year": "值", "previous_year": "值", "yoy_change": "xx%", "evidence": "证据"}}],
        "profitability": [],
        "risk": [],
        "efficiency": []
      }},
      "business_scope_evidence": ["证据1", "证据2"]
    }}
  ],
  "notes": "无法匹配的说明"
}}

约束：
1) selected_segments 只能从模板的 segment_id 中选择。
2) segments 里的 segment_id 也只能来自模板；如无把握可空数组。
3) 不得编造数据，缺失用 "/"。
4) 只输出JSON。
"""
    response = await llm.achat([
        ChatMessage(role="system", content="你是业务结构识别与指标映射助手，必须严格输出JSON。"),
        ChatMessage(role="user", content=prompt)
    ])
    content = _extract_llm_content(response)
    parsed = _extract_json_from_text(content) or {}
    return {
        "industry": industry,
        "selected_segments": parsed.get("selected_segments") or [],
        "reasoning": parsed.get("reasoning") or [],
        "evidence": parsed.get("evidence") or [],
        "segments": parsed.get("segments") or [],
        "notes": parsed.get("notes") or "",
    }


async def _classify_industry(
    llm: Any,
    company_name: str,
    year: str,
    overview_data: str
) -> Dict[str, Any]:
    prompt = f"""
你是一个行业识别专家，需要基于年报内容识别公司所属行业。
注意：禁止根据公司名称猜测，只能使用提供的年报文本证据。

可选行业（必须从中选择一个）：
banking, insurance, securities, manufacturing, internet_platform, service, general_corporate

输入数据（来自年报公司概况/主营业务/行业分类披露）：
{overview_data}

请输出JSON：
{{
  "industry": "banking",
  "confidence": 0.92,
  "evidence": [
    "证据1",
    "证据2"
  ]
}}
"""

    response = await llm.achat([
        ChatMessage(role="system", content="你是行业分类器，必须严格输出JSON。"),
        ChatMessage(role="user", content=prompt)
    ])
    content = _extract_llm_content(response)
    parsed = _extract_json_from_text(content) or {}
    if parsed.get("industry") not in BUSINESS_SCHEMA_TEMPLATES:
        parsed["industry"] = "general_corporate"
    try:
        validated = IndustryClassificationResult.model_validate(parsed)
        return validated.model_dump()
    except Exception:
        return {
            "industry": "general_corporate",
            "confidence": 0.5,
            "evidence": []
        }


async def _select_segments(
    llm: Any,
    industry: str,
    schema: Dict[str, Any],
    business_data: str
) -> Dict[str, Any]:
    prompt = f"""
你是企业年报“业务结构识别”模块。你会得到：
- 行业判断 industry
- 该行业的业务板块模板（segments，每个含 segment_id、segment_name、business_scope、典型产品）
- 年报业务描述文本片段

任务：从模板中选择最合适的业务板块（selected_segments），用于后续“业务-财务-战略联动”分析。

输出必须是JSON，严格匹配：
{{
  "industry": "{industry}",
  "selected_segments": ["segment_id1","segment_id2"],
  "reasoning": ["...","..."],
  "evidence": ["...","..."]
}}

规则：
1) selected_segments 只能从模板提供的 segment_id 中选
2) reasoning 是你为什么选这些板块（短句），evidence 必须引用输入文本的短句
3) 如无法匹配，返回 selected_segments=[] 且说明原因

industry = {industry}
segments template =
{json.dumps(schema, ensure_ascii=False)}

annual report snippets =
<<<
{business_data}
>>>
"""

    response = await llm.achat([
        ChatMessage(role="system", content="你是业务结构识别模块，必须严格输出JSON。"),
        ChatMessage(role="user", content=prompt)
    ])
    content = _extract_llm_content(response)
    parsed = _extract_json_from_text(content) or {}
    parsed["industry"] = industry
    try:
        validated = SegmentSelectionResult.model_validate(parsed)
        return validated.model_dump()
    except Exception:
        return {
            "industry": industry,
            "selected_segments": [],
            "reasoning": [],
            "evidence": []
        }


def _filter_schema_by_segments(schema: Dict[str, Any], selected_segments: list) -> Dict[str, Any]:
    if not selected_segments:
        return schema
    filtered_segments = [
        seg for seg in schema.get("segments", [])
        if seg.get("segment_id") in selected_segments
    ]
    if not filtered_segments:
        return schema
    filtered_schema = dict(schema)
    filtered_schema["segments"] = filtered_segments
    return filtered_schema


async def _map_metrics_to_schema(
    llm: Any,
    schema: Dict[str, Any],
    business_data: str,
    overview_data: str,
    industry: str
) -> Dict[str, Any]:
    logger.info(
        f"🔎 [business_highlights] 指标映射输入概览: "
        f"business_data_len={len(business_data)}, overview_data_len={len(overview_data)}"
    )
    if not business_data:
        logger.warning("⚠️ [business_highlights] business_data 为空，指标映射可能失败")
    if not overview_data:
        logger.warning("⚠️ [business_highlights] overview_data 为空，指标映射可能失败")
    logger.info(
        "🧾 [business_highlights] business_data_snippet: "
        + (business_data[:800].replace("\n", " ") if business_data else "<empty>")
    )
    logger.info(
        "🧾 [business_highlights] overview_data_snippet: "
        + (overview_data[:800].replace("\n", " ") if overview_data else "<empty>")
    )

    segment_rules = {}
    for segment in schema.get("segments", []):
        segment_id = segment.get("segment_id")
        if not segment_id:
            continue
        rule = _get_metric_rule(industry, segment_id)
        if rule:
            segment_rules[segment_id] = rule

    prompt = f"""
你是年报指标映射助手，需要把年报中的业务数据映射到指定业务模板。

业务模板：
{json.dumps(schema, ensure_ascii=False)}

年报业务相关文本（主营业务、分部信息、业务结构、产品服务）：
{business_data}

年报公司概况补充：
{overview_data}

业务指标提取规则（必选优先，必须覆盖；可选尽量补齐）：
{json.dumps(segment_rules, ensure_ascii=False)}

请输出JSON：
{{
  "segments": [
    {{
      "segment_id": "retail_banking",
      "segment_name": "零售银行业务",
      "mapped_metrics": {{
        "scale": [{{"metric": "零售营业收入", "current_year": "xxx", "previous_year": "xxx", "yoy_change": "xx%", "evidence": "..."}}],
        "profitability": [{{"metric": "零售净息差", "current_year": "xxx", "previous_year": "xxx", "yoy_change": "xx%", "evidence": "..."}}],
        "risk": [{{"metric": "零售不良率", "current_year": "xxx", "previous_year": "xxx", "yoy_change": "xx%", "evidence": "..."}}],
        "efficiency": [{{"metric": "客户数", "current_year": "xxx", "previous_year": "xxx", "yoy_change": "xx%", "evidence": "..."}}]
      }},
      "business_scope_evidence": ["证据1", "证据2"]
    }}
  ],
  "notes": "无法匹配的指标或缺失说明"
}}
"""

    response = await llm.achat([
        ChatMessage(role="system", content="你是指标映射助手，必须严格输出JSON。"),
        ChatMessage(role="user", content=prompt)
    ])
    content = _extract_llm_content(response)
    parsed = _extract_json_from_text(content)
    return parsed or {"segments": [], "notes": "未能解析指标映射结果"}


def _build_highlights_prompt(
    company_name: str,
    year: str,
    schema: Dict[str, Any],
    metrics_mapping: Dict[str, Any],
    strategy_data: str
) -> str:
    prev_year_label = str(int(year) - 1) if year.isdigit() else "上年"
    return f"""
你是资深业务分析师，需要基于业务模板与年报数据输出业务亮点。

业务模板：
{json.dumps(schema, ensure_ascii=False)}

指标映射结果：
{json.dumps(metrics_mapping, ensure_ascii=False)}

战略/发展规划信息：
{strategy_data}

请输出结构化业务亮点（JSON）：
{{
  "highlights": [
    {{
      "business_type": "业务类型名称",
      "highlights": "业务亮点详细描述",
      "achievements": ["成就1", "成就2"]
    }}
  ],
  "overall_summary": "业务亮点总结文字",
  "key_metrics_summary": {
    "title": "关键业务指标汇总",
    "headers": ["业务板块", "关键指标", "{year}", "{prev_year_label}", "同比变动"],
    "rows": [
      ["业务板块A", "指标名称", "当前值", "上年值", "同比"],
      ["业务板块B", "指标名称", "当前值", "上年值", "同比"]
    ]
  }
}}

要求：
1. 每个业务板块输出3-5条亮点，必须结合指标映射结果
2. 体现业务-财务-战略联动（例如：业务增长驱动→财务表现→战略方向）
3. 不要编造未提供的数据
4. 必须输出 key_metrics_summary，无法提取的值用"/"占位
5. 输出必须是有效JSON，仅输出JSON
"""


def _build_performance_prompt(
    company_name: str,
    year: str,
    industry: str,
    selected_schema: Dict[str, Any],
    extracted_metrics: list,
    strategy_data: str
) -> str:
    return f"""
你是“业务板块财务表现与战略联动”自动写作与结构化输出模块。
请基于输入数据，为每个业务板块生成结构化洞察，并给出第四部分总览。

输出必须是JSON，并严格匹配以下结构：
{{
  "company_name": "{company_name}",
  "fiscal_year": "{year}",
  "industry": "{industry}",
  "overall_summary": "...",
  "segment_insights": [
    {{
      "segment_id": "...",
      "headline": "...",
      "contribution": ["..."],
      "drivers": ["..."],
      "strategy_link": ["..."],
      "risks_and_watchlist": ["..."]
    }}
  ]
}}

写作与推理规则：
1) headline 为一句话定性（例：转型阵痛/增长引擎/非息支柱/现金牛承压等），不要超过20字
2) contribution 必须明确“对全公司/全行”的影响（支撑/拖累 + 具体指标）
3) drivers 用“因果链”表达，优先从给定数据中推断，禁止编造新数据
4) strategy_link 必须把“战略动作”与“财务结果”一一对应（可多条）
5) risks_and_watchlist 给出风险点 + 可跟踪指标（尽量可量化）

selected segment templates =
{json.dumps(selected_schema, ensure_ascii=False)}

extracted metrics by segment =
{json.dumps(extracted_metrics, ensure_ascii=False)}

strategy snippets =
<<<
{strategy_data}
>>>
"""


def _build_unified_highlights_and_performance_prompt(
    company_name: str,
    year: str,
    industry: str,
    selected_schema: Dict[str, Any],
    metrics_mapping: Dict[str, Any],
    extracted_metrics: list,
    strategy_data: str
) -> str:
    prev_year_label = str(int(year) - 1) if year.isdigit() else "上年"
    return f"""
你是资深业务分析师。请一次性输出“业务亮点 + 业务财务战略联动”两部分JSON。
不得编造数据；无法确认的数值使用"/"；仅输出JSON。

company_name: {company_name}
year: {year}
industry: {industry}

selected schema:
{json.dumps(selected_schema, ensure_ascii=False)}

metrics mapping:
{json.dumps(metrics_mapping, ensure_ascii=False)}

extracted metrics:
{json.dumps(extracted_metrics, ensure_ascii=False)}

strategy snippets:
<<<
{strategy_data}
>>>

输出JSON结构（严格遵守）：
{{
  "business_highlights": {{
    "highlights": [
      {{
        "business_type": "业务板块",
        "highlights": "亮点描述",
        "achievements": ["成就1", "成就2"]
      }}
    ],
    "overall_summary": "总体结论",
    "key_metrics_summary": {{
      "title": "关键业务指标汇总",
      "headers": ["业务板块", "关键指标", "{year}", "{prev_year_label}", "同比变动"],
      "rows": [["板块", "指标", "值", "值", "值"]]
    }}
  }},
  "business_performance_report": {{
    "company_name": "{company_name}",
    "fiscal_year": "{year}",
    "industry": "{industry}",
    "overall_summary": "结构变化总结",
    "segment_insights": [
      {{
        "segment_id": "segment_id",
        "headline": "一句话结论",
        "contribution": ["对全公司贡献/拖累"],
        "drivers": ["驱动链条"],
        "strategy_link": ["战略动作->财务结果"],
        "risks_and_watchlist": ["风险点+跟踪指标"]
      }}
    ]
  }}
}}
"""


def _build_extracted_metrics(metrics_mapping: Dict[str, Any]) -> list:
    extracted_list = []
    for segment in metrics_mapping.get("segments", []):
        metrics: Dict[str, Any] = {}
        sources: Dict[str, list] = {}
        mapped_metrics = segment.get("mapped_metrics", {})
        for category, items in mapped_metrics.items():
            if not isinstance(items, list):
                continue
            for item in items:
                metric_name = item.get("metric")
                if not metric_name:
                    continue
                metrics[metric_name] = {
                    "current_year": item.get("current_year") or item.get("value"),
                    "previous_year": item.get("previous_year"),
                    "yoy_change": item.get("yoy_change"),
                    "category": category
                }
                evidence = item.get("evidence")
                if evidence:
                    sources[metric_name] = [evidence]
        try:
            extracted = ExtractedSegmentMetrics.model_validate({
                "segment_id": segment.get("segment_id"),
                "metrics": metrics,
                "sources": sources
            })
            extracted_list.append(extracted.model_dump())
        except Exception:
            extracted_list.append({
                "segment_id": segment.get("segment_id"),
                "metrics": metrics,
                "sources": sources
            })
    return extracted_list


def _build_segment_tables(
    metrics_mapping: Dict[str, Any],
    year: str,
    performance_report: Dict[str, Any],
    industry: str
) -> list:
    if year.isdigit():
        prev_year_label = str(int(year) - 1)
    else:
        prev_year_label = "上年"

    headers = ["指标", year, prev_year_label, "同比变动"]
    conclusion_by_segment = {}
    for insight in performance_report.get("segment_insights", []):
        segment_id = insight.get("segment_id")
        if segment_id:
            conclusion_by_segment[segment_id] = insight.get("headline") or insight.get("drivers", [])

    segment_tables = []
    for segment in metrics_mapping.get("segments", []):
        segment_id = segment.get("segment_id")
        segment_name = segment.get("segment_name", segment_id)
        rows = []
        mapped_metrics = segment.get("mapped_metrics", {})
        mapped_lookup = {}
        for category, items in mapped_metrics.items():
            if not isinstance(items, list):
                continue
            for item in items:
                metric_name = item.get("metric")
                if not metric_name:
                    continue
                mapped_lookup[_normalize_metric_name(metric_name)] = item

        rule = _get_metric_rule(industry, segment_id) or {}
        required_metrics = rule.get("required", [])
        optional_metrics = rule.get("optional", [])
        ordered_metrics = required_metrics + optional_metrics
        used_metrics = set()

        for metric in ordered_metrics:
            metric_name = metric.get("name")
            if not metric_name:
                continue
            item = mapped_lookup.get(_normalize_metric_name(metric_name))
            current_value = item.get("current_year") if item else "/"
            if not current_value and item:
                current_value = item.get("value") or "/"
            previous_value = item.get("previous_year") if item else "/"
            yoy_change = item.get("yoy_change") if item else "/"
            rows.append([metric_name, current_value or "/", previous_value or "/", yoy_change or "/"])
            used_metrics.add(_normalize_metric_name(metric_name))
        for category in ["scale", "profitability", "risk", "efficiency"]:
            items = mapped_metrics.get(category, [])
            if not isinstance(items, list):
                continue
            for item in items:
                metric_name = item.get("metric")
                if not metric_name:
                    continue
                if _normalize_metric_name(metric_name) in used_metrics:
                    continue
                current_value = item.get("current_year") or item.get("value") or "/"
                previous_value = item.get("previous_year") or "/"
                yoy_change = item.get("yoy_change") or "/"
                rows.append([metric_name, current_value, previous_value, yoy_change])

        conclusion = conclusion_by_segment.get(segment_id, "")
        if isinstance(conclusion, list):
            conclusion = "；".join(conclusion)
        if not conclusion:
            conclusion = "业务结论待补充"

        table = {
            "title": f"{segment_name}指标",
            "headers": headers,
            "rows": rows,
            "insight": conclusion
        }
        segment_tables.append({
            "segment_id": segment_id,
            "segment_name": segment_name,
            "table": table,
            "conclusion": conclusion
        })

    return segment_tables


def _build_key_metrics_summary(segment_tables: list, year: str) -> Dict[str, Any]:
    if year.isdigit():
        prev_year_label = str(int(year) - 1)
    else:
        prev_year_label = "上年"

    headers = ["业务板块", "关键指标", year, prev_year_label, "同比变动"]
    rows = []
    for segment in segment_tables or []:
        segment_name = segment.get("segment_name") or segment.get("segment_id") or "业务板块"
        table_rows = (segment.get("table") or {}).get("rows") or []
        picked = None
        for row in table_rows:
            if not row or len(row) < 2:
                continue
            metric_name = row[0]
            if metric_name and metric_name not in ("/", "-", "—"):
                picked = row
                break
        if picked:
            rows.append([
                segment_name,
                picked[0],
                picked[1] if len(picked) > 1 else "/",
                picked[2] if len(picked) > 2 else "/",
                picked[3] if len(picked) > 3 else "/"
            ])
        else:
            rows.append([segment_name, "暂无", "/", "/", "/"])

    if not rows:
        rows = [["暂无", "暂无", "/", "/", "/"]]

    return {
        "title": "关键业务指标汇总",
        "headers": headers,
        "rows": rows
    }


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    return []


def _split_findings(text: str, limit: int = 4) -> List[str]:
    if not text:
        return []
    parts = re.split(r"[。；\n]", str(text))
    cleaned = [p.strip(" -\t\r") for p in parts if p and p.strip()]
    return cleaned[:limit]


def _build_visualization_payload(
    segment_tables: List[Dict[str, Any]],
    key_metrics_summary: Dict[str, Any],
    performance_report: Dict[str, Any]
) -> Dict[str, Any]:
    segment_insights = _safe_list(performance_report.get("segment_insights"))

    growth_items = []
    strategy_items = []
    risk_items = []
    growth_findings: List[str] = []
    strategy_findings: List[str] = []
    risk_findings: List[str] = []

    for idx, insight in enumerate(segment_insights):
        if not isinstance(insight, dict):
            continue
        segment_id = insight.get("segment_id") or f"segment-{idx}"
        segment_name = insight.get("segment_name") or segment_id
        headline = str(insight.get("headline") or "").strip()
        contribution = insight.get("contribution")
        if isinstance(contribution, list):
            contribution_text = "；".join([str(i).strip() for i in contribution if str(i).strip()])
        else:
            contribution_text = str(contribution or "").strip()
        drivers = insight.get("drivers")
        if isinstance(drivers, list):
            drivers_text = "；".join([str(i).strip() for i in drivers if str(i).strip()])
        else:
            drivers_text = str(drivers or "").strip()

        growth_items.append({
            "segment_id": segment_id,
            "segment_name": segment_name,
            "headline": headline or "业务亮点待补充",
            "contribution": contribution_text or "贡献信息待补充",
        })
        growth_findings.append(f"{segment_name}：{headline or contribution_text or '亮点待补充'}")

        strategy_links = _safe_list(insight.get("strategy_link"))
        if strategy_links:
            strategy_items.append({
                "segment_id": segment_id,
                "segment_name": segment_name,
                "action_count": len(strategy_links),
                "top_actions": strategy_links[:2],
            })
            strategy_findings.append(f"{segment_name}：{'；'.join([str(x) for x in strategy_links[:2]])}")
        elif drivers_text:
            strategy_findings.append(f"{segment_name}：{drivers_text}")

        risk_lines = _safe_list(insight.get("risks_and_watchlist"))
        for line in risk_lines[:2]:
            line_text = str(line).strip()
            if not line_text:
                continue
            risk_items.append({
                "risk": line_text,
                "impact": segment_name,
                "probability": "中",
            })
            risk_findings.append(f"{segment_name}：{line_text}")

    summary_title = str((key_metrics_summary or {}).get("title") or "关键业务指标汇总")
    overall_summary = str(performance_report.get("overall_summary") or "").strip()

    visualization_spec = {
        "growth_engine": {
            "chart_type": "insight_cards",
            "view_type": "insight_cards",
            "purpose": "展示各业务板块的一句话结论与贡献",
            "items": growth_items,
        },
        "metric_anchor": {
            "chart_type": "financial_table",
            "view_type": "financial_table",
            "purpose": "展示关键业务指标汇总与分板块指标表",
            "summary_title": summary_title,
            "key_metrics_summary_table": key_metrics_summary or {},
            "segment_tables": [
                {
                    "segment_id": table.get("segment_id"),
                    "segment_name": table.get("segment_name"),
                    "table": table.get("table"),
                    "conclusion": table.get("conclusion"),
                }
                for table in _safe_list(segment_tables)
                if isinstance(table, dict)
            ],
        },
        "strategic_execution": {
            "chart_type": "status_bar",
            "view_type": "status_bar",
            "purpose": "展示各业务板块战略动作数量与重点动作",
            "items": strategy_items,
        },
        "uncertainty_boundary": {
            "chart_type": "risk_matrix",
            "view_type": "risk_matrix",
            "purpose": "展示各业务板块风险关注项",
            "items": risk_items,
        },
    }

    visualization_insights = {
        "growth_engine": {
            "insights": [{
                "insight_type": "comparison",
                "description": overall_summary or "各业务板块呈现差异化增长与贡献特征",
                "key_findings": growth_findings[:4] or ["业务亮点待补充"],
                "related_items": [item.get("segment_name") for item in growth_items[:4] if item.get("segment_name")] or ["业务板块"],
            }]
        },
        "metric_anchor": {
            "insights": [{
                "insight_type": "trend",
                "description": "关键业务指标用于锚定各板块当前经营表现",
                "key_findings": _split_findings("；".join(growth_findings[:4])) or ["关键业务指标待补充"],
                "related_items": [summary_title],
            }]
        },
        "strategic_execution": {
            "insights": [{
                "insight_type": "comparison",
                "description": "战略动作与经营结果形成映射关系",
                "key_findings": strategy_findings[:4] or ["战略动作待补充"],
                "related_items": [item.get("segment_name") for item in strategy_items[:4] if item.get("segment_name")] or ["战略动作"],
            }]
        },
        "uncertainty_boundary": {
            "insights": [{
                "insight_type": "anomaly",
                "description": "风险关注项主要来自各板块经营与资产质量变化",
                "key_findings": risk_findings[:4] or ["风险关注项待补充"],
                "related_items": [item.get("impact") for item in risk_items[:4] if item.get("impact")] or ["风险项"],
            }]
        },
    }

    return {
        "visualization_spec": visualization_spec,
        "visualization_insights": visualization_insights,
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
        logger.info(f"开始生成业务亮点(提速版): {company_name} {year}年")
        start_time = time.time()
        retrieval_time = 0.0
        llm_time = 0.0
        retrieval_count = 0
        retrieval_success_count = 0
        llm_calls_total = 0

        def time_remaining() -> float:
            return MAX_TOTAL_SECONDS - (time.time() - start_time)

        llm = Settings.llm

        # Step 1: 三段检索并行执行（overview / business / strategy）
        overview_query = (
            f"{company_name} {year}年 公司概况 主营业务描述 行业分类披露 "
            "证监会行业 中信行业 主营业务范围"
        )
        business_query = f"{company_name} {year}年 分部信息 业务板块 业务结构 业务收入 主要产品 服务"
        strategy_query = f"{company_name} {year}年 发展战略 经营计划 战略规划 竞争优势"
        retrieval_count += 3
        q_start = time.time()
        overview_data, business_data, strategy_data = await asyncio.gather(
            _run_with_timeout(_run_query_with_timeout(query_engine, overview_query, QUERY_TIMEOUT_SECONDS), QUERY_TIMEOUT_SECONDS + 1, "", "公司概况检索"),
            _run_with_timeout(_run_query_with_timeout(query_engine, business_query, QUERY_TIMEOUT_SECONDS), QUERY_TIMEOUT_SECONDS + 1, "", "业务结构检索"),
            _run_with_timeout(_run_query_with_timeout(query_engine, strategy_query, QUERY_TIMEOUT_SECONDS), QUERY_TIMEOUT_SECONDS + 1, "", "战略检索"),
        )
        retrieval_time += time.time() - q_start
        if str(overview_data).strip():
            retrieval_success_count += 1
        if str(business_data).strip():
            retrieval_success_count += 1
        if str(strategy_data).strip():
            retrieval_success_count += 1

        # Step 2: 行业识别（规则优先，LLM兜底收紧）
        inferred_industry = _infer_industry_from_company_name(company_name)
        if inferred_industry:
            industry_result = {
                "industry": inferred_industry,
                "confidence": 0.85,
                "evidence": ["company_name_rule"]
            }
        else:
            heuristic_industry = _infer_industry_from_overview_text(overview_data)
            if heuristic_industry:
                industry_result = {
                    "industry": heuristic_industry,
                    "confidence": 0.75,
                    "evidence": ["overview_keyword_rule"]
                }
            elif len(str(overview_data or "")) >= INDUSTRY_LLM_MIN_TEXT_LEN and time_remaining() > (LLM_TIMEOUT_SECONDS / 2):
                llm_calls_total += 1
                llm_start = time.time()
                industry_result = await _run_with_timeout(
                    _classify_industry(llm, company_name, year, str(overview_data)),
                    LLM_TIMEOUT_SECONDS,
                    {"industry": "general_corporate", "confidence": 0.5, "evidence": []},
                    "行业识别"
                )
                llm_time += time.time() - llm_start
            else:
                industry_result = {
                    "industry": "general_corporate",
                    "confidence": 0.45,
                    "evidence": ["llm_fallback_skipped_for_speed"]
                }

        industry = industry_result.get("industry", "general_corporate")
        schema = get_business_schema(industry)

        # Step 3: 合并LLM调用（板块选择 + 指标映射）
        segment_rules = _build_segment_rules(schema, industry)
        llm_calls_total += 1
        llm_start = time.time()
        mapping_result = await _run_with_timeout(
            _select_segments_and_map_metrics(
                llm=llm,
                industry=industry,
                schema=schema,
                business_data=str(business_data),
                overview_data=str(overview_data),
                segment_rules=segment_rules
            ),
            LLM_TIMEOUT_SECONDS,
            {
                "industry": industry,
                "selected_segments": [],
                "reasoning": [],
                "evidence": [],
                "segments": [],
                "notes": "板块识别与指标映射超时",
            },
            "板块识别与指标映射"
        )
        llm_time += time.time() - llm_start

        segment_selection = {
            "industry": industry,
            "selected_segments": mapping_result.get("selected_segments", []),
            "reasoning": mapping_result.get("reasoning", []),
            "evidence": mapping_result.get("evidence", []),
        }
        selected_schema = _filter_schema_by_segments(schema, segment_selection.get("selected_segments", []))
        metrics_mapping = {
            "segments": mapping_result.get("segments", []),
            "notes": mapping_result.get("notes", ""),
        }

        if ENABLE_RULE_ENRICH:
            metrics_mapping = await _enrich_metrics_with_rules(
                metrics_mapping,
                industry,
                company_name,
                year,
                query_engine,
                time_remaining
            )
        else:
            logger.info("⏭️ [business_highlights] 已关闭规则补检索(BH_ENABLE_RULE_ENRICH=0)")

        if not metrics_mapping.get("segments"):
            fallback_segments = []
            for segment in selected_schema.get("segments", []):
                segment_id = segment.get("segment_id")
                segment_name = segment.get("segment_name", segment_id)
                if not segment_id:
                    continue
                fallback_segments.append({
                    "segment_id": segment_id,
                    "segment_name": segment_name,
                    "mapped_metrics": {}
                })
            metrics_mapping["segments"] = fallback_segments
            metrics_mapping.setdefault("notes", "指标抽取为空，已使用模板板块生成占位表格")

        extracted_metrics = _build_extracted_metrics(metrics_mapping)

        # Step 4: 合并LLM调用（业务亮点 + 联动报告）
        llm_calls_total += 1
        llm_start = time.time()
        unified_prompt = _build_unified_highlights_and_performance_prompt(
            company_name=company_name,
            year=year,
            industry=industry,
            selected_schema=selected_schema,
            metrics_mapping=metrics_mapping,
            extracted_metrics=extracted_metrics,
            strategy_data=str(strategy_data),
        )
        unified_response = await _run_with_timeout(
            llm.achat([
                ChatMessage(role="system", content="你是业务分析师，必须严格输出JSON。"),
                ChatMessage(role="user", content=unified_prompt)
            ]),
            LLM_TIMEOUT_SECONDS,
            "",
            "业务亮点与联动报告"
        )
        llm_time += time.time() - llm_start

        unified_content = _extract_llm_content(unified_response)
        unified_parsed = _extract_json_from_text(unified_content) or {}

        raw_highlights = unified_parsed.get("business_highlights")
        if not isinstance(raw_highlights, dict):
            raw_highlights = unified_parsed if isinstance(unified_parsed, dict) else {}

        result_dict = _validate_and_clean_data(raw_highlights, BusinessHighlights)
        if not isinstance(result_dict, dict) or not result_dict:
            result_dict = {
                "highlights": [],
                "overall_summary": "业务亮点生成失败，已降级",
                "key_metrics_summary": {}
            }

        default_perf = {
            "company_name": company_name,
            "fiscal_year": year,
            "industry": industry,
            "overall_summary": "",
            "segment_insights": []
        }
        performance_parsed = unified_parsed.get("business_performance_report")
        if not isinstance(performance_parsed, dict):
            performance_parsed = default_perf
        try:
            performance_report = BusinessPerformanceReport.model_validate(performance_parsed).model_dump()
        except Exception:
            performance_report = performance_parsed or default_perf

        segment_tables = _build_segment_tables(
            metrics_mapping,
            year,
            performance_report if isinstance(performance_report, dict) else {},
            industry
        )
        key_metrics_summary = _build_key_metrics_summary(segment_tables, year)
        if not result_dict.get("key_metrics_summary"):
            result_dict["key_metrics_summary"] = key_metrics_summary

        visualization_payload = _build_visualization_payload(
            segment_tables,
            key_metrics_summary,
            performance_report if isinstance(performance_report, dict) else {}
        )

        extra_payload = {
            "company_name": company_name,
            "year": year,
            "industry": industry_result.get("industry"),
            "industry_confidence": industry_result.get("confidence"),
            "industry_evidence": industry_result.get("evidence"),
            "selected_segments": segment_selection.get("selected_segments", []),
            "segment_selection_evidence": segment_selection.get("evidence", []),
            "extracted_segment_metrics": extracted_metrics,
            "business_performance_report": performance_report,
            "metrics_mapping_notes": metrics_mapping.get("notes"),
            "segment_tables": segment_tables,
            "key_metrics_summary": key_metrics_summary,
            "visualization_spec": visualization_payload.get("visualization_spec"),
            "visualization_insights": visualization_payload.get("visualization_insights")
        }
        result_dict.update(extra_payload)

        total_time = time.time() - start_time
        result_dict["perf_stats"] = {
            "retrieval_time_seconds": round(retrieval_time, 2),
            "llm_time_seconds": round(llm_time, 2),
            "total_time_seconds": round(total_time, 2),
            "retrieval_count": retrieval_count,
            "retrieval_success_count": retrieval_success_count,
            "llm_calls_total": llm_calls_total,
            "enable_rule_enrich": ENABLE_RULE_ENRICH,
            "rule_enrich_max_queries": RULE_ENRICH_MAX_QUERIES,
            "timeouts": {
                "query_timeout_seconds": QUERY_TIMEOUT_SECONDS,
                "llm_timeout_seconds": LLM_TIMEOUT_SECONDS,
                "max_total_seconds": MAX_TOTAL_SECONDS,
            }
        }

        return result_dict

    except Exception as e:
        logger.error(f"❌ 生成业务亮点失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "error": f"生成业务亮点失败: {str(e)}",
            "company_name": company_name,
            "year": year,
            "segment_tables": [],
            "key_metrics_summary": _build_key_metrics_summary([], year)
        }
