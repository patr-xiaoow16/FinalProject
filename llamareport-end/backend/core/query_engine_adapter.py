from types import SimpleNamespace
from typing import Any, Dict, Optional

from core.contracts import QueryContext


class CachedQueryEngineAdapter:
    """Adapter with the same .query interface, backed by shared RetrievalHub."""

    def __init__(self, raw_query_engine, retrieval_hub, scene: str = "general", profile: str = "section_deep"):
        self._raw = raw_query_engine
        self._hub = retrieval_hub
        self._scene = scene
        self._profile = profile

    def query(
        self,
        question: str,
        context_filter: Optional[Dict[str, Any]] = None,
        top_k: int = 20,
    ):
        bundle = self._hub.retrieve(
            QueryContext(
                scene=self._scene,
                question=question,
                context_filter=context_filter,
                profile=self._profile,
                top_k=top_k,
            )
        )
        # Keep compatibility with places expecting response.response and source_nodes
        source_nodes = [
            SimpleNamespace(
                text=s.get("text", ""),
                metadata=s.get("metadata", {}),
                score=s.get("score", 0.0),
            )
            for s in bundle.sources
        ]
        answer_text = bundle.metadata.get("answer") if isinstance(bundle.metadata, dict) else ""
        if not answer_text:
            answer_text = bundle.context_text or ""
        return SimpleNamespace(response=answer_text, source_nodes=source_nodes)

    def __getattr__(self, name: str):
        return getattr(self._raw, name)
