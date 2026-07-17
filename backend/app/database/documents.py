from __future__ import annotations

import uuid
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
