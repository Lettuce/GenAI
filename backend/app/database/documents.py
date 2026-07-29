from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.document_chunk import DocumentChunk
from app.database.models.source_document import SourceDocument


@dataclass(frozen=True)
class PassageRow:
    chunk_id: uuid.UUID
    source_document_id: uuid.UUID
    content: str
    page_number: int | None
    ticker: str | None
    company_name: str | None
    filing_type: str | None
    filing_year: int | None
    filing_date_iso: str | None
    accession_number: str | None
    source_url: str | None


@dataclass(frozen=True)
class NeighborPassageRow:
    chunk_id: uuid.UUID
    content: str
    page_number: int | None


def get_passage_rows(db: Session, chunk_ids: list[uuid.UUID]) -> list[PassageRow]:
    if not chunk_ids:
        return []

    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.source_document_id,
            DocumentChunk.content,
            DocumentChunk.page_number,
            SourceDocument.ticker,
            SourceDocument.company_name,
            SourceDocument.filing_type,
            SourceDocument.filing_year,
            SourceDocument.filing_date,
            SourceDocument.accession_number,
            SourceDocument.source_url,
        )
        .join(SourceDocument, SourceDocument.id == DocumentChunk.source_document_id)
        .where(DocumentChunk.id.in_(chunk_ids))
    )

    rows = db.execute(stmt).all()

    by_chunk_id: dict[uuid.UUID, PassageRow] = {}
    for row in rows:
        filing_date_iso = row[8].isoformat() if row[8] is not None else None
        by_chunk_id[row[0]] = PassageRow(
            chunk_id=row[0],
            source_document_id=row[1],
            content=row[2],
            page_number=row[3],
            ticker=row[4],
            company_name=row[5],
            filing_type=row[6],
            filing_year=row[7],
            filing_date_iso=filing_date_iso,
            accession_number=row[9],
            source_url=row[10],
        )

    ordered_rows: list[PassageRow] = []
    for chunk_id in chunk_ids:
        row = by_chunk_id.get(chunk_id)
        if row is not None:
            ordered_rows.append(row)

    return ordered_rows


def get_neighbor_passage_rows(
    db: Session,
    *,
    seed_chunk_ids: list[uuid.UUID],
    window: int,
) -> dict[uuid.UUID, list[NeighborPassageRow]]:
    if not seed_chunk_ids or window <= 0:
        return {}

    seed_stmt = select(
        DocumentChunk.id,
        DocumentChunk.source_document_id,
    ).where(DocumentChunk.id.in_(seed_chunk_ids))
    seed_rows = db.execute(seed_stmt).all()
    if not seed_rows:
        return {}

    seed_to_document: dict[uuid.UUID, uuid.UUID] = {row[0]: row[1] for row in seed_rows}
    by_document_id: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for chunk_id, document_id in seed_to_document.items():
        by_document_id[document_id].append(chunk_id)

    ordered_chunks_stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.source_document_id,
            DocumentChunk.content,
            DocumentChunk.page_number,
        )
        .where(DocumentChunk.source_document_id.in_(list(by_document_id.keys())))
        .order_by(DocumentChunk.source_document_id.asc(), DocumentChunk.created_at.asc(), DocumentChunk.id.asc())
    )
    ordered_chunk_rows = db.execute(ordered_chunks_stmt).all()

    chunks_by_document: dict[uuid.UUID, list[NeighborPassageRow]] = defaultdict(list)
    position_index_by_document: dict[uuid.UUID, dict[uuid.UUID, int]] = defaultdict(dict)
    for row in ordered_chunk_rows:
        document_chunks = chunks_by_document[row[1]]
        position_index_by_document[row[1]][row[0]] = len(document_chunks)
        document_chunks.append(
            NeighborPassageRow(
                chunk_id=row[0],
                content=row[2],
                page_number=row[3],
            )
        )

    neighbors_by_seed: dict[uuid.UUID, list[NeighborPassageRow]] = {}
    for seed_chunk_id, document_id in seed_to_document.items():
        document_chunks = chunks_by_document.get(document_id, [])
        chunk_positions = position_index_by_document.get(document_id, {})
        seed_index = chunk_positions.get(seed_chunk_id)
        if seed_index is None:
            continue

        start_index = max(0, seed_index - window)
        end_index = min(len(document_chunks), seed_index + window + 1)
        neighbors = [
            chunk
            for position, chunk in enumerate(document_chunks[start_index:end_index], start=start_index)
            if position != seed_index
        ]
        neighbors_by_seed[seed_chunk_id] = neighbors

    return neighbors_by_seed
