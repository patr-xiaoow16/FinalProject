"""
业绩指引章节生成工具（重构版）

目标：
- 基于可核验年报材料生成“四板块”洞察
- 同时输出可视化生成指令
- 保持前端兼容字段：BusinessGuidance + visualization_spec + visualization_insights + perf_stats
"""

import asyncio
import json
import logging
import re
import time
from typing import Annotated, Any, Dict, List, Optional

from llama_index.core import Settings
from llama_index.core.llms import ChatMessage

from agents.report_common import _validate_and_clean_data
from models.report_models import BusinessGuidance

logger = logging.getLogger(__name__)


def _extract_json_object(text: str) -> Dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        return {}
    raw = text.strip()
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass

    # 尝试从代码块/自由文本中提取 JSON 主体
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _split_findings(text: str, limit: int = 4) -> List[str]:
    if not text:
        return []
    parts = re.split(r"[。；\n]", text)
    cleaned = [p.strip(" -\t\r") for p in parts if p and p.strip()]
    return cleaned[:limit]


def _safe_items(items: Any) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


async def _retrieve_only(query_engine: Any, question: str, top_k: int, timeout_seconds: float) -> str:
    """只做检索，不触发 query_engine.query（避免额外LLM）。"""
    try:
        hub = getattr(query_engine, "_hub", None)
        rag = getattr(hub, "rag_engine", None) if hub is not None else None

        # 优先混合检索
        hybrid = getattr(rag, "hybrid_retriever", None) if rag is not None else None
        if (
            rag is not None
            and getattr(rag, "use_hybrid_retriever", False)
            and hybrid is not None
            and getattr(hybrid, "text_index", None) is not None
            and getattr(hybrid, "table_index", None) is not None
        ):
            results = await asyncio.wait_for(
                asyncio.to_thread(hybrid.retrieve, question, top_k, "auto", None),
                timeout=timeout_seconds,
            )
            snippets: List[str] = []
            for item in (results or [])[:top_k]:
                doc = item.get("document") if isinstance(item, dict) else None
                if not doc:
                    continue
                text = _to_text(getattr(doc, "text", ""))
                if text:
                    snippets.append(text[:800])
            return "\n\n".join(snippets)

        # 退化到向量检索器
        if rag is not None and getattr(rag, "index", None) is not None:
            retriever = rag.index.as_retriever(similarity_top_k=top_k)
            nodes = await asyncio.wait_for(
                asyncio.to_thread(retriever.retrieve, question),
                timeout=timeout_seconds,
            )
            snippets = []
            for node in (nodes or [])[:top_k]:
                text = _to_text(getattr(node, "text", ""))
                if text:
                    snippets.append(text[:800])
            return "\n\n".join(snippets)

        logger.warning("⚠️ [business_guidance] 无可用纯检索器，返回空材料")
        return ""
    except asyncio.TimeoutError:
        logger.warning("⚠️ [business_guidance] 检索超时: %s", question[:80])
        return ""
    except Exception as exc:
        logger.warning("⚠️ [business_guidance] 检索失败: %s", exc)
        return ""


async def generate_business_guidance(
    company_name: Annotated[str, "公司名称"],
    year: Annotated[str, "年份"],
    query_engine: Any,
) -> Dict[str, Any]:
    """重构版业绩指引生成：四板块洞察 + 可视化指令。"""
    start_total = time.time()
    retrieval_count = 4
    llm_calls_insight = 1
    llm_calls_visualization = 1

    try:
        logger.info("开始生成业绩指引(重构版): %s %s年", company_name, year)

        top_k = 8
        timeout_seconds = 12.0

        q1 = f"{company_name} {year}年 业绩指引 经营目标 经营计划 业绩预告"
        q2 = f"{company_name} {year}年 核心指标 营业收入 净利润 ROE 净息差 不良率 资本充足率"
        q3 = f"{company_name} {year}年 业务结构 调整 转型 零售 对公 同业 关键举措"
        q4 = f"{company_name} {year}年 风险提示 不确定性 资产质量 拨备 资本 流动性"

        start_retrieval = time.time()
        ctx_goal, ctx_metric, ctx_path, ctx_risk = await asyncio.gather(
            _retrieve_only(query_engine, q1, top_k, timeout_seconds),
            _retrieve_only(query_engine, q2, top_k, timeout_seconds),
            _retrieve_only(query_engine, q3, top_k, timeout_seconds),
            _retrieve_only(query_engine, q4, top_k, timeout_seconds),
        )
        retrieval_time = time.time() - start_retrieval
        retrieval_success_count = sum(1 for c in [ctx_goal, ctx_metric, ctx_path, ctx_risk] if str(c).strip())

        llm = Settings.llm

        prompt = f"""
你是一名专业的金融分析师。请基于给定年报材料，生成“业绩指引洞察与可视化生成指令”。

任务要求：
1. 围绕四个固定板块输出：
   - operating_goal（经营目标方向）
   - key_metrics（核心指标锚点）
   - execution_path（关键执行路径）
   - uncertainty（不确定性与边界）
2. 洞察必须为结论型文字，必须引用可核验数值。
3. 不得预测未来，不得编造数据。
4. 若数据不足，必须写“数据不足，无法生成洞察”。
5. 只输出 JSON，不要任何解释与代码块。

公司：{company_name}
年份：{year}

材料-经营目标方向：
{ctx_goal[:5000]}

材料-核心指标锚点：
{ctx_metric[:5000]}

材料-关键执行路径：
{ctx_path[:5000]}

材料-不确定性与边界：
{ctx_risk[:5000]}

输出 JSON 结构（严格遵守）：
{{
  "guidance_period": "{year}年度",
  "metrics": {{
    "parent_net_profit_range": null,
    "parent_net_profit_growth_range": null,
    "non_recurring_profit_range": null,
    "eps_range": null,
    "revenue_range": null
  }},
  "sections": {{
    "operating_goal": {{
      "insight": "1段结论，至少3个具体数值，并明确进攻/防守/转型",
      "visualization": {{
        "view_type": "status_card",
        "chart_type": "status_card",
        "purpose": "展示公司当前经营阶段与目标优先级",
        "key_elements": ["经营阶段", "风险/盈利/规模优先级"],
        "stage": "进攻/防守/转型",
        "priority": ["风险控制", "盈利稳定", "规模增长"]
      }}
    }},
    "key_metrics": {{
      "insight": "1段结论，至少3个指标数据",
      "visualization": {{
        "view_type": "status_bar",
        "chart_type": "status_bar",
        "purpose": "展示核心指标方向、当前值和同比变化",
        "key_elements": ["指标", "当前值", "同比变化"],
        "items": [{{"name": "指标", "value": "数值", "trend": "up/down/flat", "note": "变化解读"}}]
      }}
    }},
    "execution_path": {{
      "insight": "1段结论，说明如何落实目标",
      "visualization": {{
        "view_type": "structure_change",
        "chart_type": "structure_change",
        "purpose": "展示结构迁移与执行动作",
        "key_elements": ["执行动作", "证据", "影响"],
        "items": [{{"action": "动作", "evidence": "证据"}}]
      }}
    }},
    "uncertainty": {{
      "insight": "1段结论，至少2个风险相关指标",
      "visualization": {{
        "view_type": "risk_matrix",
        "chart_type": "risk_matrix",
        "purpose": "展示风险、影响对象与概率",
        "key_elements": ["风险", "影响对象", "概率"],
        "items": [{{"risk": "风险", "impact": "影响对象", "probability": "高/中/低"}}]
      }}
    }}
  }}
}}
"""

        start_llm = time.time()
        response = await llm.achat([
            ChatMessage(role="system", content="你是专业金融分析师，只输出JSON。"),
            ChatMessage(role="user", content=prompt),
        ])
        llm_time = time.time() - start_llm

        response_text = response.message.content if hasattr(response, "message") else str(response)
        payload = _extract_json_object(_to_text(response_text))

        sections = payload.get("sections") if isinstance(payload.get("sections"), dict) else {}
        operating = sections.get("operating_goal") if isinstance(sections.get("operating_goal"), dict) else {}
        metrics_sec = sections.get("key_metrics") if isinstance(sections.get("key_metrics"), dict) else {}
        path_sec = sections.get("execution_path") if isinstance(sections.get("execution_path"), dict) else {}
        risk_sec = sections.get("uncertainty") if isinstance(sections.get("uncertainty"), dict) else {}

        operating_insight = _to_text(operating.get("insight"), "数据不足，无法生成洞察")
        metrics_insight = _to_text(metrics_sec.get("insight"), "数据不足，无法生成洞察")
        path_insight = _to_text(path_sec.get("insight"), "数据不足，无法生成洞察")
        risk_insight = _to_text(risk_sec.get("insight"), "数据不足，无法生成洞察")

        metrics_obj = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
        guidance_period = _to_text(payload.get("guidance_period"), f"{year}年度")

        key_metric_items = _safe_items((metrics_sec.get("visualization") or {}).get("items"))
        key_metric_lines = []
        for item in key_metric_items[:6]:
            name = _to_text(item.get("name"), "指标")
            value = _to_text(item.get("value"), "-")
            trend = _to_text(item.get("trend"), "")
            note = _to_text(item.get("note"), "")
            tail = "；".join([x for x in [f"趋势:{trend}" if trend else "", note] if x])
            key_metric_lines.append(f"{name}：{value}{('（' + tail + '）') if tail else ''}")

        exec_items = _safe_items((path_sec.get("visualization") or {}).get("items"))
        exec_lines = []
        for item in exec_items[:6]:
            action = _to_text(item.get("action"), "执行动作")
            evidence = _to_text(item.get("evidence"), "")
            exec_lines.append(f"{action}{('：' + evidence) if evidence else ''}")

        risk_items = _safe_items((risk_sec.get("visualization") or {}).get("items"))
        risk_lines = []
        for item in risk_items[:6]:
            risk = _to_text(item.get("risk"), "风险")
            impact = _to_text(item.get("impact"), "")
            prob = _to_text(item.get("probability"), "")
            tail = "；".join([x for x in [f"影响:{impact}" if impact else "", f"概率:{prob}" if prob else ""] if x])
            risk_lines.append(f"{risk}{('（' + tail + '）') if tail else ''}")

        visualization_spec = {
            "operating_goal": {
                "chart_type": _to_text((operating.get("visualization") or {}).get("chart_type"), "status_card"),
                "view_type": _to_text((operating.get("visualization") or {}).get("view_type"), "status_card"),
                "purpose": _to_text((operating.get("visualization") or {}).get("purpose"), "展示公司当前经营阶段与目标优先级"),
                "key_elements": (operating.get("visualization") or {}).get("key_elements") or [],
                "stage": _to_text((operating.get("visualization") or {}).get("stage"), ""),
                "priority": (operating.get("visualization") or {}).get("priority") or [],
            },
            "key_metrics": {
                "chart_type": _to_text((metrics_sec.get("visualization") or {}).get("chart_type"), "status_bar"),
                "view_type": _to_text((metrics_sec.get("visualization") or {}).get("view_type"), "status_bar"),
                "purpose": _to_text((metrics_sec.get("visualization") or {}).get("purpose"), "展示核心指标方向、当前值和同比变化"),
                "key_elements": (metrics_sec.get("visualization") or {}).get("key_elements") or [],
                "items": key_metric_items,
            },
            "execution_path": {
                "chart_type": _to_text((path_sec.get("visualization") or {}).get("chart_type"), "structure_change"),
                "view_type": _to_text((path_sec.get("visualization") or {}).get("view_type"), "structure_change"),
                "purpose": _to_text((path_sec.get("visualization") or {}).get("purpose"), "展示结构迁移与执行动作"),
                "key_elements": (path_sec.get("visualization") or {}).get("key_elements") or [],
                "items": exec_items,
            },
            "uncertainty": {
                "chart_type": _to_text((risk_sec.get("visualization") or {}).get("chart_type"), "risk_matrix"),
                "view_type": _to_text((risk_sec.get("visualization") or {}).get("view_type"), "risk_matrix"),
                "purpose": _to_text((risk_sec.get("visualization") or {}).get("purpose"), "展示风险、影响对象与概率"),
                "key_elements": (risk_sec.get("visualization") or {}).get("key_elements") or [],
                "items": risk_items,
            },
        }

        visualization_insights = {
            "operating_goal": {
                "insights": [{
                    "insight_type": "comparison",
                    "description": operating_insight,
                    "key_findings": _split_findings(operating_insight),
                    "related_items": ["经营阶段/基调"],
                }]
            },
            "key_metrics": {
                "insights": [{
                    "insight_type": "trend",
                    "description": metrics_insight,
                    "key_findings": _split_findings(metrics_insight),
                    "related_items": [
                        _to_text(item.get("name"), "指标") for item in key_metric_items[:4]
                    ] or ["核心指标"],
                }]
            },
            "execution_path": {
                "insights": [{
                    "insight_type": "comparison",
                    "description": path_insight,
                    "key_findings": _split_findings(path_insight),
                    "related_items": [
                        _to_text(item.get("action"), "执行动作") for item in exec_items[:4]
                    ] or ["执行动作"],
                }]
            },
            "uncertainty": {
                "insights": [{
                    "insight_type": "anomaly",
                    "description": risk_insight,
                    "key_findings": _split_findings(risk_insight),
                    "related_items": [
                        _to_text(item.get("risk"), "风险") for item in risk_items[:4]
                    ] or ["风险"],
                }]
            },
        }

        result_dict = BusinessGuidance(
            guidance_period=guidance_period,
            expected_performance=operating_insight,
            parent_net_profit_range=_to_text(metrics_obj.get("parent_net_profit_range"), None),
            parent_net_profit_growth_range=_to_text(metrics_obj.get("parent_net_profit_growth_range"), None),
            non_recurring_profit_range=_to_text(metrics_obj.get("non_recurring_profit_range"), None),
            eps_range=_to_text(metrics_obj.get("eps_range"), None),
            revenue_range=_to_text(metrics_obj.get("revenue_range"), None),
            key_metrics=[metrics_insight] + key_metric_lines if key_metric_lines else [metrics_insight],
            business_specific_guidance=[path_insight] + exec_lines if exec_lines else [path_insight],
            risk_warnings=[risk_insight] + risk_lines if risk_lines else [risk_insight],
            visualization_spec=visualization_spec,
            visualization_insights=visualization_insights,
        ).model_dump()

        result_dict["company_name"] = company_name
        result_dict["year"] = year

        total_time = time.time() - start_total
        result_dict["perf_stats"] = {
            "retrieval_time_seconds": round(retrieval_time, 2),
            "llm_time_seconds": round(llm_time, 2),
            "total_time_seconds": round(total_time, 2),
            "retrieval_count": retrieval_count,
            "retrieval_success_count": retrieval_success_count,
            "llm_calls_insight": llm_calls_insight,
            "llm_calls_visualization": llm_calls_visualization,
            "llm_calls_total": llm_calls_insight + llm_calls_visualization,
        }

        result_dict = _validate_and_clean_data(result_dict, BusinessGuidance)

        logger.info(
            "📊 [PERF][business_guidance_v2] retrieval_time=%.2fs, llm_time=%.2fs, total_time=%.2fs, retrieval_count=%d, llm_calls_insight=%d, llm_calls_visualization=%d",
            retrieval_time,
            llm_time,
            total_time,
            retrieval_count,
            llm_calls_insight,
            llm_calls_visualization,
        )
        return result_dict

    except Exception as exc:
        total_time = time.time() - start_total
        logger.error("❌ 生成业绩指引失败: %s", exc)
        logger.exception(exc)
        return {
            "guidance_period": f"{year}年度",
            "expected_performance": "数据不足，无法生成洞察",
            "key_metrics": ["数据不足，无法生成洞察"],
            "business_specific_guidance": ["数据不足，无法生成洞察"],
            "risk_warnings": ["数据不足，无法生成洞察"],
            "company_name": company_name,
            "year": year,
            "perf_stats": {
                "retrieval_time_seconds": 0,
                "llm_time_seconds": 0,
                "total_time_seconds": round(total_time, 2),
                "retrieval_count": 0,
                "retrieval_success_count": 0,
                "llm_calls_insight": 0,
                "llm_calls_visualization": 0,
                "llm_calls_total": 0,
            },
            "error": str(exc),
        }
