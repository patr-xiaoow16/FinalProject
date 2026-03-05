from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class QueryContext:
    scene: str
    question: str
    context_filter: Optional[Dict[str, Any]] = None
    top_k: int = 10
    profile: str = "default"


@dataclass
class EvidenceBundle:
    retrieval_id: str
    question: str
    enhanced_query: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    context_text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
