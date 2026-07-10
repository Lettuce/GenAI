from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models.document_chunk import DocumentChunk
from app.database.models.source_document import SourceDocument

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT.parent / "data" / "downloads"
MANIFEST_PATH = DATA_DIR / "manifest.json"


@dataclass
class IngestionResult:
    source_document_id: str
    chunk_count: int


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def _parse_filing_date(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return datetime.fromisoformat(value)
        return None


def _extract_company_name(html: str) -> str | None:
    match = re.search(r"<dei:EntityRegistrantName[^>]*>([^<]+)<", html, re.I)
    if match:
        return _normalize_text(match.group(1))
    match = re.search(r"<companyName[^>]*>([^<]+)<", html, re.I)
    if match:
        return _normalize_text(match.group(1))
    return None


def extract_filing_metadata(manifest_entry: dict[str, Any], filing_year: int | None = None) -> dict[str, Any]:
    filing_date_value = _parse_filing_date(manifest_entry.get("filing_date"))
    filing_year_value = filing_year or (filing_date_value.year if filing_date_value is not None else None)

    return {
        "ticker": _normalize_text(manifest_entry.get("ticker")),
        "company_name": None,
        "filing_type": _normalize_text(manifest_entry.get("form")),
        "filing_year": filing_year_value,
        "accession_number": _normalize_text(manifest_entry.get("accession_number")),
        "source_url": _normalize_text(manifest_entry.get("source_url")),
        "filing_date": filing_date_value,
    }


class MarkdownHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self._skip_depth = 0
        self._current_heading: str | None = None
        self._current_text: list[str] = []
        self._current_list_item: list[str] = []
        self._current_paragraph: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if tag in {"h1", "h2", "h3", "h4"}:
            self._current_heading = tag
            self._current_text = []
            return
        if tag == "p":
            self._current_paragraph = []
            return
        if tag == "li":
            self._current_list_item = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if tag in {"h1", "h2", "h3", "h4"} and self._current_heading == tag:
            text = self._clean_text(self._current_text)
            if text:
                prefix = "#" * int(tag[1])
                self.lines.append(f"{prefix} {text}")
            self._current_heading = None
            self._current_text = []
            return
        if tag == "p":
            text = self._clean_text(self._current_paragraph)
            if text:
                self.lines.append(text)
            self._current_paragraph = []
            return
        if tag == "li":
            text = self._clean_text(self._current_list_item)
            if text:
                self.lines.append(f"- {text}")
            self._current_list_item = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        text = data.strip()
        if not text:
            return
        if self._current_heading is not None:
            self._current_text.append(text)
        elif self._current_paragraph:
            self._current_paragraph.append(text)
        elif self._current_list_item:
            self._current_list_item.append(text)
        else:
            self._current_paragraph = [text]

    def _clean_text(self, parts: list[str]) -> str:
        return " ".join(" ".join(parts).split())


def parse_html_to_markdown(html: str) -> str:
    parser = MarkdownHTMLParser()
    parser.feed(html)
    parser.close()
    return "\n\n".join(parser.lines).strip()


def chunk_markdown(markdown: str, max_chars: int = 1200) -> list[str]:
    if not markdown.strip():
        return []

    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", markdown) if paragraph.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        paragraph_len = len(paragraph)
        if current and current_len + paragraph_len + 1 > max_chars:
            chunks.append("\n\n".join(current).strip())
            current = []
            current_len = 0

        current.append(paragraph)
        current_len += paragraph_len + 1

    if current:
        chunks.append("\n\n".join(current).strip())

    return chunks


def _load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_filing_html(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8", errors="ignore")


def _build_fallback_embedding(text: str, dimensions: int = settings.embedding_dimensions) -> list[float]:
    values: list[float] = []
    for index in range(dimensions):
        digest = hashlib.sha256(f"{text}:{index}".encode("utf-8")).digest()
        values.append(((digest[0] / 255.0) * 2.0) - 1.0)
    return values


def _create_embedding(text: str, client: OpenAI) -> list[float]:
    try:
        response = client.embeddings.create(model=settings.embedding_model, input=text)
        return response.data[0].embedding
    except Exception as exc:  # pragma: no cover - exercised via live quota failures
        status_code = getattr(exc, "status_code", None)
        if isinstance(exc, httpx.HTTPStatusError):
            response = exc.response
            status_code = response.status_code if response is not None else None
        if isinstance(exc, APIStatusError) and status_code not in {429, 500, 502, 503, 504}:
            raise
        if isinstance(exc, httpx.HTTPStatusError) and status_code not in {429, 500, 502, 503, 504}:
            raise
        if not isinstance(exc, (APIConnectionError, APITimeoutError, APIStatusError, RateLimitError, httpx.HTTPStatusError)):
            raise
        print(
            f"OpenAI embedding call failed ({exc}); using deterministic fallback embedding for {len(text)} characters.",
            file=sys.stderr,
        )
        return _build_fallback_embedding(text, dimensions=settings.embedding_dimensions)


def _embed_chunks(chunks: list[str], client: OpenAI) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for chunk in chunks:
        embeddings.append(_create_embedding(chunk, client))
    return embeddings


def ingest_manifest(manifest_path: Path = MANIFEST_PATH, database_url: str | None = None) -> list[IngestionResult]:
    manifest = _load_manifest(manifest_path)
    engine = create_engine(database_url or settings.database_url)
    client = OpenAI(api_key=settings.openai_api_key, max_retries=0)

    results: list[IngestionResult] = []
    with Session(engine) as session:
        for filing in manifest.get("filings", []):
            local_path = filing.get("local_path")
            if not local_path:
                continue

            file_path = DATA_DIR / Path(local_path.replace("\\", "/"))
            if not file_path.exists():
                continue

            html = _load_filing_html(file_path)
            markdown = parse_html_to_markdown(html)
            metadata = extract_filing_metadata(filing, filing_year=None)
            metadata["company_name"] = _extract_company_name(html)
            chunks = chunk_markdown(markdown)

            accession_number = metadata["accession_number"]
            stmt = select(SourceDocument).where(SourceDocument.accession_number == accession_number)
            document = session.scalar(stmt)

            if document is None:
                document = SourceDocument(
                    ticker=metadata["ticker"],
                    company_name=metadata["company_name"],
                    filing_type=metadata["filing_type"],
                    filing_year=metadata["filing_year"],
                    accession_number=accession_number,
                    filing_date=metadata["filing_date"],
                    source_url=metadata["source_url"],
                    full_markdown_content=markdown,
                )
                session.add(document)
                session.flush()
            else:
                document.ticker = metadata["ticker"]
                document.company_name = metadata["company_name"] or document.company_name
                document.filing_type = metadata["filing_type"]
                document.filing_year = metadata["filing_year"]
                document.filing_date = metadata["filing_date"]
                document.source_url = metadata["source_url"]
                document.full_markdown_content = markdown
                session.add(document)
                session.flush()

            session.execute(
                DocumentChunk.__table__.delete().where(DocumentChunk.source_document_id == document.id)
            )
            session.flush()

            embeddings = _embed_chunks(chunks, client)
            for index, chunk in enumerate(chunks):
                session.add(
                    DocumentChunk(
                        source_document_id=document.id,
                        content=chunk,
                        embedding=embeddings[index],
                        page_number=index + 1,
                    )
                )

            session.commit()
            session.execute(
                update(DocumentChunk)
                .where(DocumentChunk.source_document_id == document.id)
                .values(search_vector=func.to_tsvector('english', DocumentChunk.content))
            )
            session.commit()
            results.append(IngestionResult(source_document_id=str(document.id), chunk_count=len(chunks)))

    return results


if __name__ == "__main__":
    results = ingest_manifest()
    print(json.dumps([{"source_document_id": item.source_document_id, "chunk_count": item.chunk_count} for item in results], indent=2))
