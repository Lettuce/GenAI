from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, func, select, update
from sqlalchemy.orm import Session

from app.schemas.config import settings
from app.database.models.document_chunk import DocumentChunk
from app.database.models.source_document import SourceDocument
from ingest.chunking import build_chunkers, chunk_document
from ingest.embeddings import build_embedding_client, embed_texts


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT.parent / "data" / "downloads" / "markdown"
MANIFEST_PATH = DATA_DIR / "manifest.json"


@dataclass
class IngestionResult:
    source_document_id: str
    chunk_count: int


def _load_manifest(path: Path = MANIFEST_PATH) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_file_path(local_path: str) -> Path:
    return DATA_DIR / Path(local_path.replace("\\", "/"))


def _manifest_filing_date(value: object) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def ingest_manifest(manifest_path: Path = MANIFEST_PATH, database_url: str | None = None) -> list[IngestionResult]:
    manifest = _load_manifest(manifest_path)
    engine = create_engine(database_url or settings.database_url)
    client = build_embedding_client()
    results: list[IngestionResult] = []

    with Session(engine) as session:
        for filing in manifest.get("filings", []):
            local_path = filing.get("local_path")
            if not local_path:
                continue

            file_path = _resolve_file_path(local_path)
            if not file_path.exists():
                continue

            chunked_document = chunk_document(file_path)
            _, hybrid_chunker = build_chunkers()
            embeddings_input = [hybrid_chunker.contextualize(chunk) for chunk in chunked_document.hybrid_chunks]
            embeddings = embed_texts(embeddings_input, client)

            accession_number = filing.get("accession_number")
            filing_date = chunked_document.filing_date or _manifest_filing_date(filing.get("filing_date"))
            stmt = select(SourceDocument).where(SourceDocument.accession_number == accession_number)
            document = session.scalar(stmt)

            if document is None:
                document = SourceDocument(
                    ticker=filing.get("ticker"),
                    company_name=None,
                    filing_type=filing.get("form"),
                    filing_year=filing_date.year if filing_date else None,
                    accession_number=accession_number,
                    filing_date=filing_date,
                    source_url=filing.get("source_url"),
                    full_markdown_content=chunked_document.markdown_text,
                )
                session.add(document)
                session.flush()
            else:
                document.ticker = filing.get("ticker")
                document.filing_type = filing.get("form")
                document.filing_year = filing_date.year if filing_date else None
                document.filing_date = filing_date
                document.source_url = filing.get("source_url")
                document.full_markdown_content = chunked_document.markdown_text
                session.add(document)
                session.flush()

            session.execute(DocumentChunk.__table__.delete().where(DocumentChunk.source_document_id == document.id))
            session.flush()

            for index, chunk in enumerate(chunked_document.hybrid_chunks):
                session.add(
                    DocumentChunk(
                        source_document_id=document.id,
                        content=hybrid_chunker.contextualize(chunk),
                        embedding=embeddings[index],
                        page_number=index + 1,
                    )
                )

            session.commit()
            session.execute(
                update(DocumentChunk)
                .where(DocumentChunk.source_document_id == document.id)
                .values(search_vector=func.to_tsvector("english", func.left(DocumentChunk.content, 8000)))
            )
            session.commit()
            results.append(IngestionResult(source_document_id=str(document.id), chunk_count=len(chunked_document.hybrid_chunks)))

    return results


def ingest_single_file(manifest_path: Path = MANIFEST_PATH, database_url: str | None = None) -> IngestionResult | None:
    results = ingest_manifest(manifest_path=manifest_path, database_url=database_url)
    return results[0] if results else None


if __name__ == "__main__":
    results = ingest_manifest()
    print(json.dumps([{"source_document_id": item.source_document_id, "chunk_count": item.chunk_count} for item in results], indent=2))