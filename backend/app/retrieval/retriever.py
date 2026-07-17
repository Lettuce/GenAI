from __future__ import annotations

from openai import OpenAI
from sqlalchemy.orm import Session

from app.retrieval.embeddings import build_embedding_client, embed_query
from app.retrieval.fusion import fuse_ranked_candidates
from app.retrieval.passages import build_passages
from app.retrieval.queries import lexical_search, semantic_search
from app.retrieval.types import RetrievedPassage, RetrievalFilters


class HybridRetriever:
    def __init__(
        self,
        db: Session,
        *,
        embedding_client: OpenAI | None = None,
        semantic_limit: int = 30,
        lexical_limit: int = 30,
        final_limit: int = 8,
        rrf_k: int = 60,
    ) -> None:
        self._db = db
        self._embedding_client = embedding_client or build_embedding_client()
        self._semantic_limit = semantic_limit
        self._lexical_limit = lexical_limit
        self._final_limit = final_limit
        self._rrf_k = rrf_k

    def retrieve(self, query: str, *, filters: RetrievalFilters | None = None) -> list[RetrievedPassage]:
        query_embedding = embed_query(query, self._embedding_client)

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
        return build_passages(self._db, fused_candidates)

    async def aretrieve(self, query: str, *, filters: RetrievalFilters | None = None) -> list[RetrievedPassage]:
        return self.retrieve(query, filters=filters)
