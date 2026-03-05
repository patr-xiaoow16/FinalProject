"""
业务亮点章节生成工具
"""

import logging
from typing import Dict, Any, Annotated, Optional, List

import json
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

MAX_TOTAL_SECONDS = 180
QUERY_TIMEOUT_SECONDS = 35
LLM_TIMEOUT_SECONDS = 45
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

    max_queries = 12
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
        start_time = time.time()

        def time_remaining() -> float:
            return MAX_TOTAL_SECONDS - (time.time() - start_time)
        
        # Step 1: 行业识别（优先公司名规则，减少检索开销）
        inferred_industry = _infer_industry_from_company_name(company_name)
        llm = Settings.llm
        overview_data = ""
        if inferred_industry:
            industry_result = {
                "industry": inferred_industry,
                "confidence": 0.7,
                "evidence": ["company_name_rule"]
            }
            logger.info(f"🔁 [business_highlights] 行业识别命中规则: {inferred_industry}")
        else:
            overview_query = (
                f"{company_name} {year}年 公司概况 主营业务描述 行业分类披露 "
                "证监会行业 中信行业 主营业务范围"
            )
            if time_remaining() <= 0:
                raise TimeoutError("业务亮点生成超时，提前结束")
            try:
                overview_data = await _run_query_with_timeout(
                    query_engine,
                    overview_query,
                    QUERY_TIMEOUT_SECONDS
                )
            except Exception as e:
                logger.warning(f"⚠️ 业务亮点-公司概况检索失败，使用空白: {e}")
                overview_data = ""
            industry_result = await _run_with_timeout(
                _classify_industry(llm, company_name, year, str(overview_data)),
                LLM_TIMEOUT_SECONDS,
                {"industry": "general_corporate", "confidence": 0.5, "evidence": []},
                "行业识别"
            )
        logger.info(f"✅ 业务亮点行业识别: {industry_result.get('industry')}，置信度: {industry_result.get('confidence')}")
        
        # Step 2: 业务拆分模板选择
        schema = get_business_schema(industry_result.get("industry", "general_corporate"))
        
        # Step 3: 业务板块数据抽取（指标映射）
        business_query = (
            f"{company_name} {year}年 分部信息 业务板块 业务结构 业务收入 主要产品 服务"
        )
        if time_remaining() <= 0:
            raise TimeoutError("业务亮点生成超时，提前结束")
        try:
            business_data = await _run_query_with_timeout(
                query_engine,
                business_query,
                QUERY_TIMEOUT_SECONDS
            )
        except Exception as e:
            logger.warning(f"⚠️ 业务亮点-业务结构检索失败，使用空白: {e}")
            business_data = ""
        # 不做二次检索，避免额外耗时

        segment_selection = await _run_with_timeout(
            _select_segments(
            llm,
            industry_result.get("industry", "general_corporate"),
            schema,
            str(business_data)
            ),
            LLM_TIMEOUT_SECONDS,
            {"industry": industry_result.get("industry", "general_corporate"), "selected_segments": [], "reasoning": [], "evidence": []},
            "业务板块选择"
        )
        if not segment_selection.get("selected_segments"):
            logger.warning("⚠️ 业务板块选择为空，回退到行业模板全量板块")

        selected_schema = _filter_schema_by_segments(
            schema,
            segment_selection.get("selected_segments", [])
        )

        metrics_mapping = await _run_with_timeout(
            _map_metrics_to_schema(
                llm,
                selected_schema,
                str(business_data),
                str(overview_data),
                industry_result.get("industry", "general_corporate")
            ),
            LLM_TIMEOUT_SECONDS,
            {"segments": [], "notes": "指标映射超时"},
            "指标映射"
        )
        metrics_mapping = await _enrich_metrics_with_rules(
            metrics_mapping,
            industry_result.get("industry", "general_corporate"),
            company_name,
            year,
            query_engine,
            time_remaining
        )
        if not metrics_mapping.get("segments"):
            # 没有抽取到指标时，至少保留业务板块，便于生成占位表格
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
        
        # Step 4: 业务-财务-战略联动分析
        strategy_query = f"{company_name} {year}年 发展战略 经营计划 战略规划 竞争优势"
        if time_remaining() <= 0:
            raise TimeoutError("业务亮点生成超时，提前结束")
        try:
            strategy_data = await _run_query_with_timeout(
                query_engine,
                strategy_query,
                QUERY_TIMEOUT_SECONDS
            )
        except Exception as e:
            logger.warning(f"⚠️ 业务亮点-战略检索失败，使用空白: {e}")
            strategy_data = ""
        prompt = _build_highlights_prompt(
            company_name,
            year,
            selected_schema,
            metrics_mapping,
            str(strategy_data)
        )

        # 使用结构化输出 - 添加异常处理和性能监控
        response = None
        structured_llm_start = time.time()
        try:
            sllm = llm.as_structured_llm(BusinessHighlights)
            raw_response = await _run_with_timeout(
                sllm.achat([
                    ChatMessage(role="system", content="你是一个专业的业务分析师,擅长总结业务亮点。你必须严格按照用户要求的JSON格式输出，只输出JSON，不要有任何其他文字。"),
                    ChatMessage(role="user", content=prompt)
                ]),
                LLM_TIMEOUT_SECONDS,
                {},
                "业务亮点生成"
            )
            
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
                    response = BusinessHighlights(**parsed_data) if isinstance(parsed_data, dict) and 'highlights' in parsed_data else parsed_data
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
                        response = BusinessHighlights(**parsed_data) if isinstance(parsed_data, dict) and 'highlights' in parsed_data else parsed_data
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
                normal_response = await _run_with_timeout(
                    llm.achat([
                        ChatMessage(role="system", content="你是一个专业的业务分析师,擅长总结业务亮点。你必须严格按照用户要求的JSON格式输出，只输出JSON，不要有任何其他文字。"),
                        ChatMessage(role="user", content=prompt)
                    ]),
                    LLM_TIMEOUT_SECONDS,
                    "",
                    "业务亮点回退生成"
                )
                
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
                # 返回错误信息，但不中断流程
                response = {
                    "error": f"生成失败: {str(fallback_error)}",
                    "content": content if 'content' in locals() else str(fallback_error)
                }

        logger.info(f"✅ 业务亮点生成成功")

        # Step 5: 业务-财务-战略联动（对齐 BusinessPerformanceReport）
        performance_report = {
            "company_name": company_name,
            "fiscal_year": year,
            "industry": industry_result.get("industry", "general_corporate"),
            "overall_summary": "",
            "segment_insights": []
        }
        if time_remaining() > 20:
            performance_prompt = _build_performance_prompt(
                company_name,
                year,
                industry_result.get("industry", "general_corporate"),
                selected_schema,
                extracted_metrics,
                str(strategy_data)
            )
            performance_response = await _run_with_timeout(
                llm.achat([
                    ChatMessage(role="system", content="你是业务-财务-战略联动分析专家，必须严格输出JSON。"),
                    ChatMessage(role="user", content=performance_prompt)
                ]),
                LLM_TIMEOUT_SECONDS,
                "",
                "业务-财务-战略联动"
            )
            performance_content = _extract_llm_content(performance_response)
            performance_parsed = _extract_json_from_text(performance_content) or {}
            try:
                performance_report = BusinessPerformanceReport.model_validate(performance_parsed).model_dump()
            except Exception:
                performance_report = performance_parsed or performance_report

        segment_tables = _build_segment_tables(
            metrics_mapping,
            year,
            performance_report if isinstance(performance_report, dict) else {},
            industry_result.get("industry", "general_corporate")
        )
        key_metrics_summary = _build_key_metrics_summary(segment_tables, year)
        
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
            "key_metrics_summary": key_metrics_summary
        }

        # 数据验证和清理（仅针对业务亮点结构）
        result_dict = _validate_and_clean_data(result_dict, BusinessHighlights)
        result_dict.update(extra_payload)
        
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

