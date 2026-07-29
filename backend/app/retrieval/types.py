from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RetrievalFilters:
    tickers: list[str] | None = None
    filing_years: list[int] | None = None
    filing_types: list[str] | None = None


@dataclass(frozen=True)
class RankedChunkCandidate:
    chunk_id: uuid.UUID
    source_document_id: uuid.UUID
    rank: int
    score: float


@dataclass(frozen=True)
class FusedChunkCandidate:
    chunk_id: uuid.UUID
    source_document_id: uuid.UUID
    fused_score: float
    semantic_rank: int | None
    lexical_rank: int | None
    semantic_score: float | None
    lexical_score: float | None


@dataclass(frozen=True)
class RetrievedPassage:
    chunk_id: str
    document_id: str
    content: str
    page_number: int | None
    ticker: str | None
    company_name: str | None
    filing_type: str | None
    filing_year: int | None
    filing_date: str | None
    accession_number: str | None
    source_url: str | None
    fused_score: float
    semantic_rank: int | None
    lexical_rank: int | None
    neighbor_passages: list["NeighborPassage"]


@dataclass(frozen=True)
class NeighborPassage:
    chunk_id: str
    content: str
    page_number: int | None


class RetrieverProtocol(Protocol):
    def retrieve(self, query: str, *, filters: RetrievalFilters | None = None) -> list[RetrievedPassage]: ...
