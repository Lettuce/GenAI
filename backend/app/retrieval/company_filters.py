from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.source_document import SourceDocument
from app.retrieval.types import RetrievalFilters

_COMPANY_ALIASES: dict[str, tuple[str, ...]] = {
    "AAPL": ("apple",),
    "AMZN": ("amazon",),
    "GOOGL": ("alphabet", "google", "googl", "goog"),
    "META": ("meta", "facebook"),
    "MSFT": ("microsoft", "msft"),
    "NVDA": ("nvidia", "nvda"),
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _extract_token_tickers(query_text: str) -> set[str]:
    matches: set[str] = set()
    for token in re.findall(r"[A-Za-z]{1,6}", query_text.upper()):
        if token in _COMPANY_ALIASES:
            matches.add(token)
    return matches


def _extract_alias_tickers(query_text: str) -> set[str]:
    normalized = _normalize(query_text)
    matches: set[str] = set()
    for ticker, aliases in _COMPANY_ALIASES.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", normalized):
                matches.add(ticker)
                break
    return matches


def _available_tickers(db: Session) -> set[str]:
    stmt = select(SourceDocument.ticker).where(SourceDocument.ticker.is_not(None)).distinct()
    rows = db.execute(stmt).all()
    return {row[0].upper() for row in rows if isinstance(row[0], str) and row[0].strip()}


def infer_retrieval_filters(db: Session, *, query_text: str) -> RetrievalFilters | None:
    requested = _extract_token_tickers(query_text) | _extract_alias_tickers(query_text)
    if not requested:
        return None

    available = _available_tickers(db)
    tickers = sorted(ticker for ticker in requested if ticker in available)
    if not tickers:
        return None

    return RetrievalFilters(tickers=tickers)