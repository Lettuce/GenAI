from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.documents import get_passage_rows
from app.retrieval.types import FusedChunkCandidate, RetrievedPassage


def build_passages(db: Session, fused_candidates: list[FusedChunkCandidate]) -> list[RetrievedPassage]:
    if not fused_candidates:
        return []

    chunk_ids = [candidate.chunk_id for candidate in fused_candidates]
    rows = get_passage_rows(db, chunk_ids)
    rows_by_chunk_id = {row.chunk_id: row for row in rows}

    passages: list[RetrievedPassage] = []
    for candidate in fused_candidates:
        row = rows_by_chunk_id.get(candidate.chunk_id)
        if row is None:
            continue

        passages.append(
            RetrievedPassage(
                chunk_id=str(row.chunk_id),
                document_id=str(row.source_document_id),
                content=row.content,
                page_number=row.page_number,
                ticker=row.ticker,
                company_name=row.company_name,
                filing_type=row.filing_type,
                filing_year=row.filing_year,
                filing_date=row.filing_date_iso,
                accession_number=row.accession_number,
                source_url=row.source_url,
                fused_score=candidate.fused_score,
                semantic_rank=candidate.semantic_rank,
                lexical_rank=candidate.lexical_rank,
            )
        )

    return passages
