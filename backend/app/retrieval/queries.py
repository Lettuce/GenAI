from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.database.models.document_chunk import DocumentChunk
from app.database.models.source_document import SourceDocument
from app.retrieval.types import RankedChunkCandidate, RetrievalFilters


def _apply_filters(stmt: Select, filters: RetrievalFilters | None) -> Select:
    if filters is None:
        return stmt

    if filters.tickers:
        stmt = stmt.where(SourceDocument.ticker.in_(filters.tickers))
    if filters.filing_years:
        stmt = stmt.where(SourceDocument.filing_year.in_(filters.filing_years))
    if filters.filing_types:
        stmt = stmt.where(SourceDocument.filing_type.in_(filters.filing_types))

    return stmt


def semantic_search(
    db: Session,
    *,
    query_embedding: list[float],
    limit: int,
    filters: RetrievalFilters | None = None,
) -> list[RankedChunkCandidate]:
    if limit <= 0:
        return []

    distance_expr = DocumentChunk.embedding.cosine_distance(query_embedding)

    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.source_document_id,
            distance_expr.label("score"),
        )
        .join(SourceDocument, SourceDocument.id == DocumentChunk.source_document_id)
        .where(DocumentChunk.embedding.is_not(None))
        .order_by(distance_expr.asc())
        .limit(limit)
    )
    stmt = _apply_filters(stmt, filters)

    rows = db.execute(stmt).all()
    return [
        RankedChunkCandidate(
            chunk_id=row[0],
            source_document_id=row[1],
            rank=index,
            score=float(row[2]),
        )
        for index, row in enumerate(rows, start=1)
    ]


def lexical_search(
    db: Session,
    *,
    query_text: str,
    limit: int,
    filters: RetrievalFilters | None = None,
) -> list[RankedChunkCandidate]:
    if limit <= 0:
        return []

    trimmed_query = query_text.strip()
    if not trimmed_query:
        return []

    ts_query = func.plainto_tsquery("english", trimmed_query)
    rank_expr = func.ts_rank_cd(DocumentChunk.search_vector, ts_query)

    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.source_document_id,
            rank_expr.label("score"),
        )
        .join(SourceDocument, SourceDocument.id == DocumentChunk.source_document_id)
        .where(DocumentChunk.search_vector.is_not(None))
        .where(DocumentChunk.search_vector.op("@@")(ts_query))
        .order_by(rank_expr.desc())
        .limit(limit)
    )
    stmt = _apply_filters(stmt, filters)

    rows = db.execute(stmt).all()
    return [
        RankedChunkCandidate(
            chunk_id=row[0],
            source_document_id=row[1],
            rank=index,
            score=float(row[2]),
        )
        for index, row in enumerate(rows, start=1)
    ]
