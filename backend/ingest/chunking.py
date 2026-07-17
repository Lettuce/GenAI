from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import tiktoken
from docling.chunking import HierarchicalChunker, HybridChunker
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer

from app.config import settings


@dataclass(frozen=True)
class ChunkedDocument:
    source_path: Path
    markdown_text: str
    filing_date: datetime | None
    hierarchical_chunks: list[object]
    hybrid_chunks: list[object]


def load_document(source_path: Path):
    converter = DocumentConverter()
    return converter.convert(str(source_path)).document


def build_chunkers() -> tuple[HierarchicalChunker, HybridChunker]:
    tokenizer = OpenAITokenizer(
        tokenizer=tiktoken.encoding_for_model(settings.embedding_model),
        max_tokens=8192,
    )
    return HierarchicalChunker(), HybridChunker(tokenizer=tokenizer, merge_peers=True)


def chunk_document(source_path: Path) -> ChunkedDocument:
    document = load_document(source_path)
    markdown_text = document.export_to_markdown()
    filing_date = None
    parent_name = source_path.parent.name
    file_stem = source_path.stem
    for candidate in (parent_name, file_stem):
        try:
            filing_date = datetime.fromisoformat(candidate)
            break
        except ValueError:
            continue
    hierarchical_chunker, hybrid_chunker = build_chunkers()
    hierarchical_chunks = list(hierarchical_chunker.chunk(document))
    hybrid_chunks = list(hybrid_chunker.chunk(document))
    return ChunkedDocument(
        source_path=source_path,
        markdown_text=markdown_text,
        filing_date=filing_date,
        hierarchical_chunks=hierarchical_chunks,
        hybrid_chunks=hybrid_chunks,
    )


def contextualize_chunks(chunker, chunks: list[object]) -> list[str]:
    return [chunker.contextualize(chunk) for chunk in chunks]