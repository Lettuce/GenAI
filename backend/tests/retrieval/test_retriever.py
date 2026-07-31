from __future__ import annotations

from app.retrieval.retriever import HybridRetriever
from app.retrieval.types import FusedChunkCandidate, RankedChunkCandidate, RetrievedPassage, RetrievalFilters


class _FakeClient:
    pass


class _FakeSession:
    pass


def test_hybrid_retriever_orchestrates_rrf_pipeline(monkeypatch) -> None:
    db = _FakeSession()
    embedding_client = _FakeClient()
    filters = RetrievalFilters(tickers=["MSFT"])

    call_log: list[str] = []

    def _fake_embed_query(query: str, client: object) -> list[float]:
        call_log.append("embed")
        assert query == "gross margin trend"
        assert client is embedding_client
        return [0.01, -0.02]

    def _fake_semantic_search(db_session: object, *, query_embedding: list[float], limit: int, filters: object) -> list[RankedChunkCandidate]:
        call_log.append("semantic")
        assert db_session is db
        assert query_embedding == [0.01, -0.02]
        assert limit == 30
        assert filters is filters_obj
        return [
            RankedChunkCandidate(chunk_id=chunk_id, source_document_id=doc_id, rank=1, score=0.11)
        ]

    def _fake_lexical_search(db_session: object, *, query_text: str, limit: int, filters: object) -> list[RankedChunkCandidate]:
        call_log.append("lexical")
        assert db_session is db
        assert query_text == "gross margin trend"
        assert limit == 30
        assert filters is filters_obj
        return [
            RankedChunkCandidate(chunk_id=chunk_id, source_document_id=doc_id, rank=1, score=0.91)
        ]

    def _fake_fuse(*, semantic_candidates: list[RankedChunkCandidate], lexical_candidates: list[RankedChunkCandidate], rrf_k: int, limit: int) -> list[FusedChunkCandidate]:
        call_log.append("fusion")
        assert len(semantic_candidates) == 1
        assert len(lexical_candidates) == 1
        assert rrf_k == 60
        assert limit == 8
        return [
            FusedChunkCandidate(
                chunk_id=chunk_id,
                source_document_id=doc_id,
                fused_score=0.032,
                semantic_rank=1,
                lexical_rank=1,
                semantic_score=0.11,
                lexical_score=0.91,
            )
        ]

    def _fake_build_passages(
        db_session: object,
        fused_candidates: list[FusedChunkCandidate],
        *,
        neighbor_window: int,
    ) -> list[RetrievedPassage]:
        call_log.append("passages")
        assert db_session is db
        assert len(fused_candidates) == 1
        assert neighbor_window == 2
        return [
            RetrievedPassage(
                chunk_id=str(chunk_id),
                document_id=str(doc_id),
                content="Operating margin expanded year over year.",
                page_number=12,
                ticker="MSFT",
                company_name="Microsoft",
                filing_type="10-K",
                filing_year=2024,
                filing_date="2024-07-30T00:00:00+00:00",
                accession_number="0000950170-24-000000",
                source_url="https://example.com",
                fused_score=0.032,
                semantic_rank=1,
                lexical_rank=1,
                neighbor_passages=[],
            )
        ]

    import uuid

    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    filters_obj = filters

    monkeypatch.setattr("app.retrieval.retriever.embed_query", _fake_embed_query)
    monkeypatch.setattr("app.retrieval.retriever.semantic_search", _fake_semantic_search)
    monkeypatch.setattr("app.retrieval.retriever.lexical_search", _fake_lexical_search)
    monkeypatch.setattr("app.retrieval.retriever.fuse_ranked_candidates", _fake_fuse)
    monkeypatch.setattr("app.retrieval.retriever.build_passages", _fake_build_passages)

    retriever = HybridRetriever(db, embedding_client=embedding_client, neighbor_window=2)

    passages = retriever.retrieve("gross margin trend", filters=filters_obj)

    assert len(passages) == 1
    assert passages[0].ticker == "MSFT"
    assert call_log == ["embed", "semantic", "lexical", "fusion", "passages"]


def test_hybrid_retriever_falls_back_to_lexical_when_embedding_fails(monkeypatch) -> None:
    db = _FakeSession()
    embedding_client = _FakeClient()

    call_log: list[str] = []

    def _failing_embed_query(query: str, client: object) -> list[float]:
        call_log.append("embed")
        raise RuntimeError("rate limit")

    def _fake_semantic_search(**kwargs) -> list[RankedChunkCandidate]:
        call_log.append("semantic")
        return []

    def _fake_lexical_search(db_session: object, *, query_text: str, limit: int, filters: object) -> list[RankedChunkCandidate]:
        call_log.append("lexical")
        assert db_session is db
        assert query_text == "services growth"
        assert limit == 30
        assert filters is None
        return []

    def _fake_fuse(*, semantic_candidates: list[RankedChunkCandidate], lexical_candidates: list[RankedChunkCandidate], rrf_k: int, limit: int) -> list[FusedChunkCandidate]:
        call_log.append("fusion")
        assert semantic_candidates == []
        assert lexical_candidates == []
        assert rrf_k == 60
        assert limit == 8
        return []

    def _fake_build_passages(db_session: object, fused_candidates: list[FusedChunkCandidate], *, neighbor_window: int) -> list[RetrievedPassage]:
        call_log.append("passages")
        assert db_session is db
        assert fused_candidates == []
        assert neighbor_window == 1
        return []

    monkeypatch.setattr("app.retrieval.retriever.embed_query", _failing_embed_query)
    monkeypatch.setattr("app.retrieval.retriever.semantic_search", _fake_semantic_search)
    monkeypatch.setattr("app.retrieval.retriever.lexical_search", _fake_lexical_search)
    monkeypatch.setattr("app.retrieval.retriever.fuse_ranked_candidates", _fake_fuse)
    monkeypatch.setattr("app.retrieval.retriever.build_passages", _fake_build_passages)

    retriever = HybridRetriever(db, embedding_client=embedding_client)

    passages = retriever.retrieve("services growth")

    assert passages == []
    # No semantic call is made when embeddings fail, but lexical retrieval still executes.
    assert call_log == ["embed", "lexical", "fusion", "passages"]
