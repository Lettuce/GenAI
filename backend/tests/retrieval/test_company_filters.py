from __future__ import annotations

from app.retrieval.company_filters import infer_retrieval_filters


class _FakeResult:
    def __init__(self, rows: list[tuple[str | None]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[str | None]]:
        return self._rows


class _FakeSession:
    def __init__(self, tickers: list[str | None]) -> None:
        self._tickers = tickers

    def execute(self, _stmt: object) -> _FakeResult:
        return _FakeResult([(ticker,) for ticker in self._tickers])


def test_infer_retrieval_filters_from_company_name_alias() -> None:
    session = _FakeSession(["NVDA", "MSFT"])

    filters = infer_retrieval_filters(session, query_text="What is NVIDIA guidance?")

    assert filters is not None
    assert filters.tickers == ["NVDA"]


def test_infer_retrieval_filters_from_multiple_company_names() -> None:
    session = _FakeSession(["AAPL", "MSFT", "GOOGL"])

    filters = infer_retrieval_filters(session, query_text="Compare Apple and Microsoft revenue with Google")

    assert filters is not None
    assert filters.tickers == ["AAPL", "GOOGL", "MSFT"]


def test_infer_retrieval_filters_keeps_microsoft_and_nvidia_together() -> None:
    session = _FakeSession(["MSFT", "NVDA"])

    filters = infer_retrieval_filters(session, query_text="Microsoft and NVIDIA operating margin trends across recent filings")

    assert filters is not None
    assert filters.tickers == ["MSFT", "NVDA"]


def test_infer_retrieval_filters_from_ticker_token() -> None:
    session = _FakeSession(["GOOGL"])

    filters = infer_retrieval_filters(session, query_text="Summarize GOOGL operating margin")

    assert filters is not None
    assert filters.tickers == ["GOOGL"]


def test_infer_retrieval_filters_returns_none_when_ticker_not_in_corpus() -> None:
    session = _FakeSession(["MSFT"])

    filters = infer_retrieval_filters(session, query_text="Compare NVIDIA and AMD profitability")

    assert filters is None