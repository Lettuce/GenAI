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

    @staticmethod
    def _diversify_passages(passages: list[RetrievedPassage], *, filters: RetrievalFilters | None, limit: int) -> list[RetrievedPassage]:
        if not passages or limit <= 0:
            return []
        if filters is None or not filters.tickers or len(filters.tickers) <= 1:
            return passages[:limit]

        requested_tickers = {ticker.upper() for ticker in filters.tickers}
        selected: list[RetrievedPassage] = []
        seen_ids: set[str] = set()

        for ticker in filters.tickers:
            candidate = next(
                (
                    passage for passage in passages
                    if (passage.ticker or "").upper() == ticker.upper() and passage.chunk_id not in seen_ids
                ),
                None,
            )
            if candidate is None:
                continue
            selected.append(candidate)
            seen_ids.add(candidate.chunk_id)

        for passage in passages:
            if passage.chunk_id in seen_ids:
                continue
            selected.append(passage)
            seen_ids.add(passage.chunk_id)
            if len(selected) >= limit:
                break

        if len(selected) < limit:
            for passage in passages:
                if passage.chunk_id in seen_ids:
                    continue
                selected.append(passage)
                seen_ids.add(passage.chunk_id)
                if len(selected) >= limit:
                    break

        return selected[:limit]

    def retrieve(self, query: str, *, filters: RetrievalFilters | None = None) -> list[RetrievedPassage]:
        semantic_candidates = []
        if self._semantic_limit > 0:
            try:
                query_embedding = self._embedding_fn(query, self._embedding_client)
            except Exception:
                query_embedding = None

            if query_embedding is not None:
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

        candidate_limit = self._final_limit
        if filters is not None and filters.tickers and len(filters.tickers) > 1:
            candidate_limit = max(self._final_limit * 4, self._final_limit + 8)

        fused_candidates = fuse_ranked_candidates(
            semantic_candidates=semantic_candidates,
            lexical_candidates=lexical_candidates,
            rrf_k=self._rrf_k,
            limit=candidate_limit,
        )
        passages = build_passages(self._db, fused_candidates, neighbor_window=self._neighbor_window)
        return self._diversify_passages(passages, filters=filters, limit=self._final_limit)

    async def aretrieve(self, query: str, *, filters: RetrievalFilters | None = None) -> list[RetrievedPassage]:
        return self.retrieve(query, filters=filters)
