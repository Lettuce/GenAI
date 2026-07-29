from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database.session import SessionLocal
from app.retrieval.retriever import HybridRetriever
from app.retrieval.types import RetrievalFilters
from app.schemas.config import settings


QUERY_CATALOG = [
    "How did Apple describe Services growth drivers in recent 10-K filings?",
    "How did Amazon describe AWS operating income trends across recent filings?",
    "What changed in Microsoft's Azure and AI infrastructure narrative over time?",
    "How did Alphabet's Search, YouTube Ads, and Cloud trends differ in recent 10-Ks?",
]


def _truncate(text: str, *, limit: int = 240) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _resolve_query(*, selected_query_index: int, custom_query: str | None) -> str:
    if custom_query and custom_query.strip():
        return custom_query.strip()

    if selected_query_index < 0 or selected_query_index >= len(QUERY_CATALOG):
        raise ValueError(
            f"selected_query_index must be between 0 and {len(QUERY_CATALOG) - 1}, got {selected_query_index}"
        )
    return QUERY_CATALOG[selected_query_index]


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set. Check backend/.env and app/schemas/config.py settings.")

    # Edit these values for quick manual smoke checks.
    # One query runs per script execution.
    selected_query_index = 0
    custom_query: str | None = None

    query = _resolve_query(selected_query_index=selected_query_index, custom_query=custom_query)
    tickers: list[str] | None = ["AAPL"]
    filing_years: list[int] | None = None
    filing_types: list[str] | None = ["10-K"]

    semantic_limit = 30
    lexical_limit = 30
    final_limit = 5
    rrf_k = 60
    neighbor_window = 1

    filters = RetrievalFilters(
        tickers=tickers,
        filing_years=filing_years,
        filing_types=filing_types,
    )

    with SessionLocal() as db:
        retriever = HybridRetriever(
            db,
            semantic_limit=semantic_limit,
            lexical_limit=lexical_limit,
            final_limit=final_limit,
            rrf_k=rrf_k,
            neighbor_window=neighbor_window,
        )
        passages = retriever.retrieve(query, filters=filters)

    print("Query:")
    print(f"- {query}")
    print(f"- selected_query_index={selected_query_index}")
    if custom_query:
        print("- source=custom_query")
    else:
        print("- source=QUERY_CATALOG")
    print("\nRetriever parameters:")
    print(f"- embedding_model={settings.embedding_model}")
    print(f"- semantic_limit={semantic_limit}")
    print(f"- lexical_limit={lexical_limit}")
    print(f"- final_limit={final_limit}")
    print(f"- rrf_k={rrf_k}")
    print(f"- neighbor_window={neighbor_window}")
    print("\nTop passages:")

    if not passages:
        print("- No passages returned")
        return

    for rank, passage in enumerate(passages, start=1):
        print(
            f"{rank}. ticker={passage.ticker or 'n/a'} | filing={passage.filing_type or 'n/a'} "
            f"| year={passage.filing_year or 'n/a'} | score={passage.fused_score:.6f}"
        )
        print(f"   accession={passage.accession_number or 'n/a'}")
        print(f"   page={passage.page_number if passage.page_number is not None else 'n/a'}")
        print(f"   excerpt={_truncate(passage.content)}")
        if passage.neighbor_passages:
            print(f"   neighbor={_truncate(passage.neighbor_passages[0].content)}")


if __name__ == "__main__":
    main()