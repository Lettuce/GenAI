from __future__ import annotations

from dataclasses import dataclass

from app.retrieval.types import FusedChunkCandidate, RankedChunkCandidate

DEFAULT_RRF_K = 60


@dataclass
class _FusionAccumulator:
    source_document_id: object
    fused_score: float = 0.0
    semantic_rank: int | None = None
    lexical_rank: int | None = None
    semantic_score: float | None = None
    lexical_score: float | None = None


def _rrf_score(rank: int, rrf_k: int) -> float:
    return 1.0 / float(rrf_k + rank)


def fuse_ranked_candidates(
    *,
    semantic_candidates: list[RankedChunkCandidate],
    lexical_candidates: list[RankedChunkCandidate],
    rrf_k: int = DEFAULT_RRF_K,
    limit: int | None = None,
) -> list[FusedChunkCandidate]:
    if rrf_k <= 0:
        raise ValueError("rrf_k must be positive")

    accumulators: dict[object, _FusionAccumulator] = {}

    for candidate in semantic_candidates:
        accumulator = accumulators.get(candidate.chunk_id)
        if accumulator is None:
            accumulator = _FusionAccumulator(source_document_id=candidate.source_document_id)
            accumulators[candidate.chunk_id] = accumulator
        accumulator.fused_score += _rrf_score(candidate.rank, rrf_k)
        accumulator.semantic_rank = candidate.rank
        accumulator.semantic_score = candidate.score

    for candidate in lexical_candidates:
        accumulator = accumulators.get(candidate.chunk_id)
        if accumulator is None:
            accumulator = _FusionAccumulator(source_document_id=candidate.source_document_id)
            accumulators[candidate.chunk_id] = accumulator
        accumulator.fused_score += _rrf_score(candidate.rank, rrf_k)
        accumulator.lexical_rank = candidate.rank
        accumulator.lexical_score = candidate.score

    fused: list[FusedChunkCandidate] = [
        FusedChunkCandidate(
            chunk_id=chunk_id,
            source_document_id=accumulator.source_document_id,
            fused_score=accumulator.fused_score,
            semantic_rank=accumulator.semantic_rank,
            lexical_rank=accumulator.lexical_rank,
            semantic_score=accumulator.semantic_score,
            lexical_score=accumulator.lexical_score,
        )
        for chunk_id, accumulator in accumulators.items()
    ]

    def _best_rank(candidate: FusedChunkCandidate) -> int:
        ranks = [rank for rank in (candidate.semantic_rank, candidate.lexical_rank) if rank is not None]
        return min(ranks) if ranks else 10**9

    fused.sort(
        key=lambda candidate: (
            -candidate.fused_score,
            _best_rank(candidate),
            str(candidate.chunk_id),
        )
    )

    if limit is not None:
        return fused[: max(limit, 0)]
    return fused
