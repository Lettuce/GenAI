from __future__ import annotations

import uuid

from app.database.documents import NeighborPassageRow, PassageRow
from app.retrieval.passages import build_passages
from app.retrieval.types import FusedChunkCandidate


class _FakeSession:
    pass


def test_build_passages_hydrates_in_fused_order(monkeypatch) -> None:
    chunk_1 = uuid.uuid4()
    chunk_2 = uuid.uuid4()
    document_id = uuid.uuid4()

    fused_candidates = [
        FusedChunkCandidate(
            chunk_id=chunk_2,
            source_document_id=document_id,
            fused_score=0.25,
            semantic_rank=1,
            lexical_rank=2,
            semantic_score=0.1,
            lexical_score=0.7,
        ),
        FusedChunkCandidate(
            chunk_id=chunk_1,
            source_document_id=document_id,
            fused_score=0.20,
            semantic_rank=2,
            lexical_rank=None,
            semantic_score=0.2,
            lexical_score=None,
        ),
    ]

    fake_rows = [
        PassageRow(
            chunk_id=chunk_1,
            source_document_id=document_id,
            content="chunk one",
            page_number=3,
            ticker="AAPL",
            company_name="Apple",
            filing_type="10-K",
            filing_year=2023,
            filing_date_iso="2023-11-03T00:00:00+00:00",
            accession_number="abc",
            source_url="https://example.com/1",
        ),
        PassageRow(
            chunk_id=chunk_2,
            source_document_id=document_id,
            content="chunk two",
            page_number=4,
            ticker="AAPL",
            company_name="Apple",
            filing_type="10-K",
            filing_year=2023,
            filing_date_iso="2023-11-03T00:00:00+00:00",
            accession_number="def",
            source_url="https://example.com/2",
        ),
    ]

    def _fake_get_passage_rows(db: object, chunk_ids: list[uuid.UUID]) -> list[PassageRow]:
        assert chunk_ids == [chunk_2, chunk_1]
        return fake_rows

    def _fake_get_neighbor_passage_rows(
        db: object,
        *,
        seed_chunk_ids: list[uuid.UUID],
        window: int,
    ) -> dict[uuid.UUID, list[NeighborPassageRow]]:
        assert seed_chunk_ids == [chunk_2, chunk_1]
        assert window == 1
        return {
            chunk_2: [NeighborPassageRow(chunk_id=chunk_1, content="neighbor one", page_number=3)],
            chunk_1: [NeighborPassageRow(chunk_id=chunk_2, content="neighbor two", page_number=4)],
        }

    monkeypatch.setattr("app.retrieval.passages.get_passage_rows", _fake_get_passage_rows)
    monkeypatch.setattr("app.retrieval.passages.get_neighbor_passage_rows", _fake_get_neighbor_passage_rows)

    passages = build_passages(_FakeSession(), fused_candidates)

    assert [passage.chunk_id for passage in passages] == [str(chunk_2), str(chunk_1)]
    assert passages[0].content == "chunk two"
    assert passages[1].content == "chunk one"
    assert passages[0].neighbor_passages[0].content == "neighbor one"
    assert passages[1].neighbor_passages[0].content == "neighbor two"
