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


def test_hybrid_retriever_diversifies_multi_company_results(monkeypatch) -> None:
    db = _FakeSession()
    embedding_client = _FakeClient()
    filters = RetrievalFilters(tickers=["MSFT", "AAPL"])

    def _fake_embed_query(query: str, client: object) -> list[float]:
        assert query == "compare cloud and services revenue"
        assert client is embedding_client
        return [0.0, 0.0]

    def _fake_semantic_search(db_session: object, *, query_embedding: list[float], limit: int, filters: object) -> list[RankedChunkCandidate]:
        assert db_session is db
        assert filters is filters_obj
        return [
            RankedChunkCandidate(chunk_id=uuid.uuid4(), source_document_id=uuid.uuid4(), rank=1, score=0.9),
            RankedChunkCandidate(chunk_id=uuid.uuid4(), source_document_id=uuid.uuid4(), rank=2, score=0.8),
        ]

    def _fake_lexical_search(db_session: object, *, query_text: str, limit: int, filters: object) -> list[RankedChunkCandidate]:
        assert db_session is db
        assert query_text == "compare cloud and services revenue"
        assert filters is filters_obj
        return [
            RankedChunkCandidate(chunk_id=uuid.uuid4(), source_document_id=uuid.uuid4(), rank=1, score=0.7),
            RankedChunkCandidate(chunk_id=uuid.uuid4(), source_document_id=uuid.uuid4(), rank=2, score=0.6),
        ]

    def _fake_fuse(*, semantic_candidates: list[RankedChunkCandidate], lexical_candidates: list[RankedChunkCandidate], rrf_k: int, limit: int) -> list[FusedChunkCandidate]:
        return [
            FusedChunkCandidate(chunk_id=semantic_candidates[0].chunk_id, source_document_id=semantic_candidates[0].source_document_id, fused_score=0.95, semantic_rank=1, lexical_rank=None, semantic_score=0.9, lexical_score=None),
            FusedChunkCandidate(chunk_id=semantic_candidates[1].chunk_id, source_document_id=semantic_candidates[1].source_document_id, fused_score=0.90, semantic_rank=2, lexical_rank=None, semantic_score=0.8, lexical_score=None),
            FusedChunkCandidate(chunk_id=lexical_candidates[0].chunk_id, source_document_id=lexical_candidates[0].source_document_id, fused_score=0.85, semantic_rank=None, lexical_rank=1, semantic_score=None, lexical_score=0.7),
            FusedChunkCandidate(chunk_id=lexical_candidates[1].chunk_id, source_document_id=lexical_candidates[1].source_document_id, fused_score=0.80, semantic_rank=None, lexical_rank=2, semantic_score=None, lexical_score=0.6),
        ]

    def _fake_build_passages(db_session: object, fused_candidates: list[FusedChunkCandidate], *, neighbor_window: int) -> list[RetrievedPassage]:
        assert db_session is db
        first, second, third, fourth = fused_candidates
        return [
            RetrievedPassage(
                chunk_id=str(first.chunk_id),
                document_id=str(first.source_document_id),
                content="Microsoft Azure grew materially.",
                page_number=10,
                ticker="MSFT",
                company_name="Microsoft",
                filing_type="10-K",
                filing_year=2024,
                filing_date="2024-07-30T00:00:00+00:00",
                accession_number="msft-2024",
                source_url="https://example.com/msft",
                fused_score=first.fused_score,
                semantic_rank=first.semantic_rank,
                lexical_rank=first.lexical_rank,
                neighbor_passages=[],
            ),
            RetrievedPassage(
                chunk_id=str(second.chunk_id),
                document_id=str(second.source_document_id),
                content="Microsoft services revenue accelerated.",
                page_number=12,
                ticker="MSFT",
                company_name="Microsoft",
                filing_type="10-K",
                filing_year=2024,
                filing_date="2024-07-30T00:00:00+00:00",
                accession_number="msft-2024-b",
                source_url="https://example.com/msft-b",
                fused_score=second.fused_score,
                semantic_rank=second.semantic_rank,
                lexical_rank=second.lexical_rank,
                neighbor_passages=[],
            ),
            RetrievedPassage(
                chunk_id=str(third.chunk_id),
                document_id=str(third.source_document_id),
                content="Apple services revenue also increased.",
                page_number=18,
                ticker="AAPL",
                company_name="Apple",
                filing_type="10-K",
                filing_year=2024,
                filing_date="2024-10-31T00:00:00+00:00",
                accession_number="aapl-2024",
                source_url="https://example.com/aapl",
                fused_score=third.fused_score,
                semantic_rank=third.semantic_rank,
                lexical_rank=third.lexical_rank,
                neighbor_passages=[],
            ),
            RetrievedPassage(
                chunk_id=str(fourth.chunk_id),
                document_id=str(fourth.source_document_id),
                content="Apple product revenue remained resilient.",
                page_number=20,
                ticker="AAPL",
                company_name="Apple",
                filing_type="10-K",
                filing_year=2024,
                filing_date="2024-10-31T00:00:00+00:00",
                accession_number="aapl-2024-b",
                source_url="https://example.com/aapl-b",
                fused_score=fourth.fused_score,
                semantic_rank=fourth.semantic_rank,
                lexical_rank=fourth.lexical_rank,
                neighbor_passages=[],
            ),
        ]

    import uuid

    filters_obj = filters

    monkeypatch.setattr("app.retrieval.retriever.embed_query", _fake_embed_query)
    monkeypatch.setattr("app.retrieval.retriever.semantic_search", _fake_semantic_search)
    monkeypatch.setattr("app.retrieval.retriever.lexical_search", _fake_lexical_search)
    monkeypatch.setattr("app.retrieval.retriever.fuse_ranked_candidates", _fake_fuse)
    monkeypatch.setattr("app.retrieval.retriever.build_passages", _fake_build_passages)

    retriever = HybridRetriever(db, embedding_client=embedding_client, final_limit=4)
    passages = retriever.retrieve("compare cloud and services revenue", filters=filters_obj)

    tickers = {passage.ticker for passage in passages}
    assert tickers == {"MSFT", "AAPL"}


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
