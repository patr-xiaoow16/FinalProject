import ast
import json
import re
from typing import Any, Dict, List, Tuple


def _normalize_source(source: Any) -> Dict[str, Any]:
    if not isinstance(source, dict):
        return {}

    text = str(source.get("text") or "").strip()
    metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
    score = source.get("score", 0.0)

    if not text and not metadata:
        return {}

    return {
        "text": text,
        "metadata": metadata,
        "score": score,
    }


def coerce_to_mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
            return dumped if isinstance(dumped, dict) else {}
        except Exception:
            return {}
    if not isinstance(value, str):
        return {}

    raw = value.strip()
    if not raw:
        return {}

    candidates = [raw]
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        try:
            parsed = ast.literal_eval(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    return {}


def _source_key(source: Dict[str, Any]) -> Tuple[str, Any, Any]:
    metadata = source.get("metadata") or {}
    return (
        source.get("text", ""),
        metadata.get("page_number") or metadata.get("page") or metadata.get("page_label"),
        metadata.get("source_file") or metadata.get("filename") or metadata.get("file_name") or metadata.get("source"),
    )


def merge_sources(*source_lists: Any, max_items: int = 12) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen = set()

    for source_list in source_lists:
        if not isinstance(source_list, list):
            continue
        for raw_source in source_list:
            source = _normalize_source(raw_source)
            if not source:
                continue
            key = _source_key(source)
            if key in seen:
                continue
            seen.add(key)
            merged.append(source)
            if len(merged) >= max_items:
                return merged

    return merged


def collect_sources_from_payload(payload: Any, max_items: int = 12) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    direct_sources = payload.get("sources")
    raw_output = payload.get("raw_output")
    raw_output_dict = coerce_to_mapping(raw_output)
    nested_sources = raw_output_dict.get("sources") if isinstance(raw_output_dict, dict) else []

    return merge_sources(direct_sources, nested_sources, max_items=max_items)
