from __future__ import annotations

import uuid

import pytest

from app.retrieval.fusion import fuse_ranked_candidates
from app.retrieval.types import RankedChunkCandidate


def test_fuse_ranked_candidates_uses_rrf_scores() -> None:
    chunk_a = uuid.uuid4()
    chunk_b = uuid.uuid4()
    chunk_c = uuid.uuid4()
    doc_id = uuid.uuid4()

    semantic = [
        RankedChunkCandidate(chunk_id=chunk_a, source_document_id=doc_id, rank=1, score=0.10),
        RankedChunkCandidate(chunk_id=chunk_b, source_document_id=doc_id, rank=2, score=0.20),
    ]
    lexical = [
        RankedChunkCandidate(chunk_id=chunk_b, source_document_id=doc_id, rank=1, score=0.90),
        RankedChunkCandidate(chunk_id=chunk_c, source_document_id=doc_id, rank=2, score=0.80),
    ]

    fused = fuse_ranked_candidates(semantic_candidates=semantic, lexical_candidates=lexical, rrf_k=60)

    assert [item.chunk_id for item in fused] == [chunk_b, chunk_a, chunk_c]
    assert fused[0].fused_score == pytest.approx((1 / 62) + (1 / 61))


def test_fuse_ranked_candidates_is_deterministic_for_ties() -> None:
    doc_id = uuid.uuid4()
    chunk_a = uuid.UUID("00000000-0000-0000-0000-000000000001")
    chunk_b = uuid.UUID("00000000-0000-0000-0000-000000000002")

    semantic = [
        RankedChunkCandidate(chunk_id=chunk_b, source_document_id=doc_id, rank=1, score=0.1),
        RankedChunkCandidate(chunk_id=chunk_a, source_document_id=doc_id, rank=1, score=0.1),
    ]

    fused = fuse_ranked_candidates(semantic_candidates=semantic, lexical_candidates=[], rrf_k=60)

    assert [item.chunk_id for item in fused] == [chunk_a, chunk_b]


def test_fuse_ranked_candidates_rejects_non_positive_rrf_k() -> None:
    with pytest.raises(ValueError, match="rrf_k must be positive"):
        fuse_ranked_candidates(semantic_candidates=[], lexical_candidates=[], rrf_k=0)
