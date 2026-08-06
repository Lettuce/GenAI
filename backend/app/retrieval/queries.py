from __future__ import annotations

import re

from sqlalchemy import Select, case, func, literal, select
from sqlalchemy.orm import Session

from app.assistant.tools import build_fts_query_terms
from app.database.models.document_chunk import DocumentChunk
from app.database.models.source_document import SourceDocument
from app.retrieval.keywords import build_keyword_query_terms, extract_keywords
from app.retrieval.types import RankedChunkCandidate, RetrievalFilters


def _build_fts_query_terms(query_text: str, *, max_terms: int = 5) -> str:
    capped_terms = min(max(3, max_terms), 5)
    return build_fts_query_terms(query_text, min_terms=3, max_terms=capped_terms)


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


def _keyword_overlap_terms(query_text: str, *, max_terms: int = 8) -> list[str]:
    raw_terms = extract_keywords(query_text, min_terms=1, max_terms=max_terms)
    cleaned_terms: list[str] = []
    seen: set[str] = set()
    for term in raw_terms:
        normalized = re.sub(r"[^a-z0-9]+", "", term.lower())
        if len(normalized) < 3:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned_terms.append(normalized)
    return cleaned_terms[:max_terms]


def _company_overlap_fallback_search(
    db: Session,
    *,
    query_text: str,
    limit: int,
    filters: RetrievalFilters | None,
) -> list[RankedChunkCandidate]:
    if filters is None or not filters.tickers or limit <= 0:
        return []

    terms = _keyword_overlap_terms(query_text)
    if not terms:
        terms = [ticker.lower() for ticker in filters.tickers]

    score_expr = literal(0)
    lowered_content = func.lower(DocumentChunk.content)
    for term in terms:
        score_expr = score_expr + case((lowered_content.like(f"%{term}%"), 1), else_=0)

    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.source_document_id,
            score_expr.label("score"),
        )
        .join(SourceDocument, SourceDocument.id == DocumentChunk.source_document_id)
        .where(SourceDocument.ticker.in_(filters.tickers))
        .where(DocumentChunk.content.is_not(None))
        .order_by(score_expr.desc(), SourceDocument.filing_date.desc().nullslast(), DocumentChunk.id.asc())
        .limit(max(limit * 6, limit))
    )

    rows = db.execute(stmt).all()
    positive_rows = [row for row in rows if int(row[2]) > 0]
    selected_rows = positive_rows if positive_rows else rows

    return [
        RankedChunkCandidate(
            chunk_id=row[0],
            source_document_id=row[1],
            rank=index,
            score=float(row[2]),
        )
        for index, row in enumerate(selected_rows[:limit], start=1)
    ]


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

    ts_query_terms = _build_fts_query_terms(trimmed_query)
    if not ts_query_terms:
        keyword_terms = build_keyword_query_terms(trimmed_query)
        if not keyword_terms:
            return []
        ts_query_terms = keyword_terms

    ts_query = func.to_tsquery("english", ts_query_terms)
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
    if not rows:
        return _company_overlap_fallback_search(
            db,
            query_text=trimmed_query,
            limit=limit,
            filters=filters,
        )

    return [
        RankedChunkCandidate(
            chunk_id=row[0],
            source_document_id=row[1],
            rank=index,
            score=float(row[2]),
        )
        for index, row in enumerate(rows, start=1)
    ]
