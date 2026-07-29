from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.retrieval.types import RetrievalFilters, RetrieverProtocol


@dataclass(frozen=True)
class AssistantRuntimeDeps:
    user_id: uuid.UUID
    thread_id: uuid.UUID
    retriever: RetrieverProtocol
    filters: RetrievalFilters | None = None
    citation_limit: int = 8
    retrieval_query: str | None = None
    retrieved_passages: list[object] = field(default_factory=list)
