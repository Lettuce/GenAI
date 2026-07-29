from __future__ import annotations

import uuid

from app.retrieval.queries import _build_fts_query_terms, lexical_search, semantic_search
from app.retrieval.types import RetrievalFilters


class _FakeResult:
    def __init__(self, rows: list[tuple[uuid.UUID, uuid.UUID, float]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[uuid.UUID, uuid.UUID, float]]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[tuple[uuid.UUID, uuid.UUID, float]]) -> None:
        self.rows = rows
        self.last_statement = None

    def execute(self, statement: object) -> _FakeResult:
        self.last_statement = statement
        return _FakeResult(self.rows)


def test_semantic_search_returns_ranked_candidates() -> None:
    rows = [
        (uuid.uuid4(), uuid.uuid4(), 0.01),
        (uuid.uuid4(), uuid.uuid4(), 0.12),
    ]
    db = _FakeSession(rows)

    candidates = semantic_search(db, query_embedding=[0.1, 0.2], limit=2)

    assert [candidate.rank for candidate in candidates] == [1, 2]
    assert [candidate.score for candidate in candidates] == [0.01, 0.12]


def test_lexical_search_returns_ranked_candidates() -> None:
    rows = [
        (uuid.uuid4(), uuid.uuid4(), 0.91),
        (uuid.uuid4(), uuid.uuid4(), 0.73),
    ]
    db = _FakeSession(rows)

    candidates = lexical_search(db, query_text="revenue by segment", limit=2)

    assert [candidate.rank for candidate in candidates] == [1, 2]
    assert [candidate.score for candidate in candidates] == [0.91, 0.73]


def test_lexical_search_returns_empty_for_blank_query() -> None:
    db = _FakeSession([])

    candidates = lexical_search(db, query_text="   ", limit=10)

    assert candidates == []


def test_build_fts_query_terms_extracts_finance_keywords() -> None:
    query = "What sources would you use to answer a question about Apple Services growth?"

    terms = _build_fts_query_terms(query)

    assert terms == "apple | services | growth"


def test_build_fts_query_terms_caps_terms_to_five() -> None:
    query = "Show quarterly operating margin and revenue growth and cash flow guidance for Microsoft"

    terms = _build_fts_query_terms(query)

    assert len(terms.split(" | ")) == 5


def test_filters_are_applied_to_query_statement() -> None:
    rows = [(uuid.uuid4(), uuid.uuid4(), 0.1)]
    db = _FakeSession(rows)

    semantic_search(
        db,
        query_embedding=[0.1, 0.2],
        limit=1,
        filters=RetrievalFilters(tickers=["MSFT"], filing_years=[2024], filing_types=["10-K"]),
    )

    statement_text = str(db.last_statement)
    assert "source_documents.ticker" in statement_text
    assert "source_documents.filing_year" in statement_text
    assert "source_documents.filing_type" in statement_text
