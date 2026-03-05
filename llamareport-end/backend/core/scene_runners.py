from typing import Any, Dict, Optional

from core.contracts import QueryContext


class MetricClickRunner:
    def __init__(self, retrieval_hub):
        self.hub = retrieval_hub

    def run(self, question: str, context_filter: Optional[Dict[str, Any]] = None, top_k: int = 10):
        return self.hub.retrieve(QueryContext(scene="metric_click", question=question, context_filter=context_filter, top_k=top_k, profile="metric_click_fast"))


class ChatRunner:
    def __init__(self, retrieval_hub):
        self.hub = retrieval_hub

    def run(self, question: str, context_filter: Optional[Dict[str, Any]] = None, top_k: int = 10):
        return self.hub.retrieve(QueryContext(scene="chat", question=question, context_filter=context_filter, top_k=top_k, profile="chat_fast"))


class QuickSectionRunner:
    def __init__(self, retrieval_hub):
        self.hub = retrieval_hub

    def run(self, question: str, context_filter: Optional[Dict[str, Any]] = None, top_k: int = 20):
        return self.hub.retrieve(QueryContext(scene="quick_section", question=question, context_filter=context_filter, top_k=top_k, profile="section_deep"))


class LinkageRunner:
    def __init__(self, retrieval_hub):
        self.hub = retrieval_hub

    def run(self, question: str, context_filter: Optional[Dict[str, Any]] = None, top_k: int = 28):
        return self.hub.retrieve(QueryContext(scene="linkage", question=question, context_filter=context_filter, top_k=top_k, profile="linkage_multi"))
