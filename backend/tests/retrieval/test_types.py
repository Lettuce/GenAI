from __future__ import annotations

import uuid

from app.retrieval.types import FusedChunkCandidate, RankedChunkCandidate, RetrievedPassage, RetrievalFilters


def test_types_can_be_constructed() -> None:
    chunk_id = uuid.uuid4()
    document_id = uuid.uuid4()

    filters = RetrievalFilters(tickers=["AAPL"], filing_years=[2023], filing_types=["10-K"])
    ranked = RankedChunkCandidate(chunk_id=chunk_id, source_document_id=document_id, rank=1, score=0.1)
    fused = FusedChunkCandidate(
        chunk_id=chunk_id,
        source_document_id=document_id,
        fused_score=0.02,
        semantic_rank=1,
        lexical_rank=None,
        semantic_score=0.1,
        lexical_score=None,
    )
    passage = RetrievedPassage(
        chunk_id=str(chunk_id),
        document_id=str(document_id),
        content="Revenue increased.",
        page_number=10,
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_year=2023,
        filing_date="2023-11-03T00:00:00+00:00",
        accession_number="0000320193-23-000106",
        source_url="https://example.com",
        fused_score=0.02,
        semantic_rank=1,
        lexical_rank=None,
    )

    assert filters.tickers == ["AAPL"]
    assert ranked.rank == 1
    assert fused.fused_score > 0
    assert passage.ticker == "AAPL"
