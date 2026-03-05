import hashlib
import json
import logging
from typing import Any, Dict, Optional

from core.contracts import QueryContext, EvidenceBundle

logger = logging.getLogger(__name__)


class RetrievalHub:
    """Shared retrieval entrance for all scenes. Only retrieval artifacts are cached."""

    def __init__(self, rag_engine):
        self.rag_engine = rag_engine

    def retrieve(self, query_ctx: QueryContext) -> EvidenceBundle:
        result = self.rag_engine.query(
            query_ctx.question,
            context_filter=query_ctx.context_filter,
            top_k=query_ctx.top_k,
            cache_profile=query_ctx.profile,
        )
        retrieval_seed = {
            "q": query_ctx.question,
            "f": query_ctx.context_filter or {},
            "p": query_ctx.profile,
            "k": query_ctx.top_k,
            "v": self.rag_engine.get_index_version() if hasattr(self.rag_engine, "get_index_version") else "unknown",
        }
        retrieval_id = hashlib.sha1(json.dumps(retrieval_seed, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        bundle = EvidenceBundle(
            retrieval_id=retrieval_id,
            question=query_ctx.question,
            enhanced_query=result.get("enhanced_query", query_ctx.question),
            sources=result.get("sources", []),
            context_text=result.get("retrieval_context", ""),
            metadata={
                "profile": query_ctx.profile,
                "error": result.get("error", False),
                "answer": result.get("answer", ""),
            },
        )
        return bundle
