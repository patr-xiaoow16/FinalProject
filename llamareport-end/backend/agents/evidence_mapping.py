import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value).strip()


def _extract_page(metadata: Dict[str, Any]) -> str:
    page_value = metadata.get("page_number") or metadata.get("page") or metadata.get("page_label")
    if page_value not in (None, ""):
        return str(page_value)

    source_str = _to_text(metadata.get("source"))
    match = re.search(r"_page_(\d+)", source_str)
    if match:
        return match.group(1)

    file_name = _to_text(metadata.get("file_name") or metadata.get("filename") or metadata.get("source_file"))
    match = re.search(r"_page_(\d+)", file_name)
    if match:
        return match.group(1)

    return ""


def extract_source_reference(source: Dict[str, Any]) -> Dict[str, str]:
    metadata = source.get("metadata", {}) if isinstance(source, dict) else {}
    evidence = _to_text(source.get("text")) if isinstance(source, dict) else ""
    if len(evidence) > 220:
        evidence = evidence[:220].rstrip() + "..."
    source_file = _to_text(
        metadata.get("source_file") or metadata.get("file_name") or metadata.get("filename") or metadata.get("source")
    )
    return {
        "evidence": evidence,
        "source_page": _extract_page(metadata),
        "source_file": source_file,
    }


def _split_claims(answer_text: str, max_items: int) -> List[str]:
    if not answer_text:
        return []
    cleaned = re.sub(r"\n+", "\n", answer_text).strip()
    parts = re.split(r"[。！？!?；;\n]+", cleaned)
    claims: List[str] = []
    for part in parts:
        claim = part.strip(" -\t\r")
        if not claim:
            continue
        claims.append(claim)
        if len(claims) >= max_items:
            break
    return claims


def fallback_evidence_mapping(answer_text: str, sources: Optional[List[Dict[str, Any]]], max_items: int = 5) -> List[Dict[str, str]]:
    claims = _split_claims(answer_text, max_items=max_items)
    refs: List[Dict[str, str]] = []
    for source in sources or []:
        ref = extract_source_reference(source)
        if ref.get("evidence"):
            refs.append(ref)
    if not claims or not refs:
        return []

    mappings: List[Dict[str, str]] = []
    for idx, claim in enumerate(claims):
        ref = refs[min(idx, len(refs) - 1)]
        mappings.append(
            {
                "claim": claim,
                "evidence": ref["evidence"],
                "source_page": ref["source_page"],
                "source_file": ref["source_file"],
            }
        )
    return mappings[:max_items]


def _extract_json_array(text: str) -> List[Dict[str, Any]]:
    if not isinstance(text, str) or not text.strip():
        return []
    raw = text.strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
    except Exception:
        pass

    match = re.search(r"\[[\s\S]*\]", raw)
    if not match:
        return []
    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
    except Exception:
        return []
    return []


def _normalize_mapping_items(items: List[Dict[str, Any]], max_items: int) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for item in items:
        claim = _to_text(item.get("claim"))
        evidence = _to_text(item.get("evidence"))
        source_page = _to_text(item.get("source_page"))
        source_file = _to_text(item.get("source_file"))
        if not claim or not evidence:
            continue
        normalized.append(
            {
                "claim": claim,
                "evidence": evidence,
                "source_page": source_page,
                "source_file": source_file,
            }
        )
        if len(normalized) >= max_items:
            break
    return normalized


def _build_messages(prompt: str) -> List[Any]:
    try:
        from llama_index.core.llms import ChatMessage

        return [
            ChatMessage(role="system", content="你是证据映射助手，只输出JSON数组，不要输出解释。"),
            ChatMessage(role="user", content=prompt),
        ]
    except Exception:
        return [
            {"role": "system", "content": "你是证据映射助手，只输出JSON数组，不要输出解释。"},
            {"role": "user", "content": prompt},
        ]


def _response_to_text(response: Any) -> str:
    if response is None:
        return ""
    for attr in ("content", "text", "response", "answer"):
        value = getattr(response, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return _to_text(response)


async def build_evidence_mapping(
    answer_text: str,
    sources: Optional[List[Dict[str, Any]]],
    llm: Optional[Any] = None,
    max_items: int = 5,
) -> List[Dict[str, str]]:
    fallback = fallback_evidence_mapping(answer_text, sources, max_items=max_items)
    if not answer_text or not sources or not llm or not hasattr(llm, "achat"):
        return fallback

    source_refs = [extract_source_reference(source) for source in sources[: min(len(sources), max_items + 2)]]
    source_lines = []
    for idx, ref in enumerate(source_refs, start=1):
        page = ref["source_page"] or "未知页码"
        file_name = ref["source_file"] or "未知来源"
        evidence = ref["evidence"] or "无证据摘录"
        source_lines.append(f"{idx}. 页码={page}; 文件={file_name}; 证据={evidence}")

    prompt = f"""
请基于给定回答和证据来源，抽取最多{max_items}条“关键结论-证据-来源页码”映射。
要求：
1. 只使用给定来源中的证据，不得编造。
2. 只输出JSON数组。
3. 每个元素必须包含 claim, evidence, source_page, source_file 四个字段。
4. claim 使用简短完整句，不要输出推理过程。

回答：
{answer_text}

来源：
{chr(10).join(source_lines)}
"""

    try:
        response = await llm.achat(_build_messages(prompt))
        raw_text = _response_to_text(response)
        parsed = _extract_json_array(raw_text)
        normalized = _normalize_mapping_items(parsed, max_items=max_items)
        return normalized or fallback
    except Exception as exc:
        logger.warning("构建 evidence mapping 失败，使用回退结果: %s", exc)
        return fallback
