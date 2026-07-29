from __future__ import annotations

from collections.abc import Callable

from openai import OpenAI
from sqlalchemy.orm import Session

from app.retrieval.embeddings import build_embedding_client, embed_query
from app.retrieval.fusion import fuse_ranked_candidates
from app.retrieval.passages import build_passages
from app.retrieval.queries import lexical_search, semantic_search
from app.retrieval.types import RetrievedPassage, RetrievalFilters
from app.schemas.config import settings


class HybridRetriever:
    def __init__(
        self,
        db: Session,
        *,
        embedding_client: OpenAI | None = None,
        embedding_fn: Callable[[str, OpenAI], list[float]] | None = None,
        semantic_limit: int = 30,
        lexical_limit: int = 30,
        final_limit: int = settings.retrieval_top_k,
        rrf_k: int = settings.rf_60,
        neighbor_window: int = 1,
    ) -> None:
        self._db = db
        self._embedding_client = embedding_client or build_embedding_client()
        self._embedding_fn = embedding_fn or embed_query
        self._semantic_limit = semantic_limit
        self._lexical_limit = lexical_limit
        self._final_limit = final_limit
        self._rrf_k = rrf_k
        self._neighbor_window = neighbor_window

    def retrieve(self, query: str, *, filters: RetrievalFilters | None = None) -> list[RetrievedPassage]:
        semantic_candidates = []
        if self._semantic_limit > 0:
            query_embedding = self._embedding_fn(query, self._embedding_client)
            semantic_candidates = semantic_search(
                self._db,
                query_embedding=query_embedding,
                limit=self._semantic_limit,
                filters=filters,
            )
        lexical_candidates = lexical_search(
            self._db,
            query_text=query,
            limit=self._lexical_limit,
            filters=filters,
        )

        fused_candidates = fuse_ranked_candidates(
            semantic_candidates=semantic_candidates,
            lexical_candidates=lexical_candidates,
            rrf_k=self._rrf_k,
            limit=self._final_limit,
        )
        return build_passages(self._db, fused_candidates, neighbor_window=self._neighbor_window)

    async def aretrieve(self, query: str, *, filters: RetrievalFilters | None = None) -> list[RetrievedPassage]:
        return self.retrieve(query, filters=filters)
