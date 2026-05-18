import re
from typing import Any, Dict, Optional


def extract_inline_source_citation(content: str) -> str:
    text = str(content or "").strip()
    if not text:
        return ""
    matches = re.findall(r"(?:数据来源|来源|参考来源|资料来源)[：:]\s*([^\n\r]+)", text)
    if not matches:
        return ""
    citation = matches[-1].strip()
    if not citation:
        return ""
    if citation.startswith("来源："):
        return citation
    return f"来源：{citation}"


def build_section_success_response(
    *,
    section_name: str,
    content: str,
    structured_response: Optional[Dict[str, Any]] = None,
    visualization: Optional[Dict[str, Any]] = None,
    tool_calls: Optional[list] = None,
    sources: Optional[list] = None,
    evidence_mapping: Optional[list] = None,
    source_citation: str = "",
) -> Dict[str, Any]:
    citation = source_citation or extract_inline_source_citation(content)
    return {
        "status": "success",
        "section_name": section_name,
        "content": content or "",
        "structured_response": structured_response,
        "visualization": visualization,
        "tool_calls": tool_calls or [],
        "sources": sources or [],
        "evidence_mapping": evidence_mapping or [],
        "source_citation": citation,
    }
