from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.chat.orchestrator import stream_grounded_turn
from app.database import chats
from app.database.session import SessionLocal
from app.retrieval.company_filters import infer_retrieval_filters
from app.retrieval.retriever import HybridRetriever

PROMPTS_BY_TICKER: dict[str, str] = {
    "AAPL": "What did Apple report about Services growth in recent filings?",
    "AMZN": "What did Amazon report about AWS operating income and growth in recent filings?",
    "GOOGL": "What did Alphabet report about Google Cloud growth and profitability in recent filings?",
    "MSFT": "What did Microsoft report about Azure growth and AI demand in recent filings?",
    "NVDA": "What did NVIDIA report about data center growth and margins in recent filings?",
}


@dataclass
class SweepResult:
    ticker: str
    inferred_tickers: list[str]
    retrieved_count: int
    retrieved_top_tickers: list[str]
    citation_count: int
    citation_tickers: list[str]
    pass_status: bool
    failure_reason: str | None


def _distinct_tickers() -> list[str]:
    with SessionLocal() as db:
        rows = db.execute(
            text("select distinct ticker from source_documents where ticker is not null order by ticker")
        ).all()
    return [row[0] for row in rows if isinstance(row[0], str) and row[0].strip()]


async def _run_ticker_check(ticker: str, prompt: str) -> SweepResult:
    user_id = uuid.uuid4()
    run_token = uuid.uuid4().hex[:8]

    with SessionLocal() as db:
        inferred = infer_retrieval_filters(db, query_text=prompt)
        inferred_tickers = inferred.tickers if inferred and inferred.tickers else []

        retriever = HybridRetriever(db)
        retrieved = retriever.retrieve(prompt, filters=inferred)
        top_tickers = [p.ticker or "" for p in retrieved[:8]]

        chats.ensure_user(db, user_id=user_id, email=f"sweep-{ticker.lower()}-{run_token}@example.com")
        thread = chats.create_thread(db, user_id=user_id, title=f"Sweep {ticker}")
        thread_id = uuid.UUID(thread.id)

        async for _ in stream_grounded_turn(db=db, thread_id=thread_id, user_text=prompt, user_id=user_id):
            pass

        messages = chats.list_messages(db, user_id=user_id, thread_id=thread_id)
        assistant_messages = [message for message in messages if message.role == "assistant"]
        if not assistant_messages:
            return SweepResult(
                ticker=ticker,
                inferred_tickers=inferred_tickers,
                retrieved_count=len(retrieved),
                retrieved_top_tickers=top_tickers,
                citation_count=0,
                citation_tickers=[],
                pass_status=False,
                failure_reason="No assistant message persisted",
            )

        latest = assistant_messages[-1]
        citation_tickers = [citation.ticker or "" for citation in latest.citations]

        if not inferred_tickers:
            return SweepResult(
                ticker=ticker,
                inferred_tickers=inferred_tickers,
                retrieved_count=len(retrieved),
                retrieved_top_tickers=top_tickers,
                citation_count=len(latest.citations),
                citation_tickers=citation_tickers,
                pass_status=False,
                failure_reason="No inferred ticker filter",
            )

        if ticker not in inferred_tickers:
            return SweepResult(
                ticker=ticker,
                inferred_tickers=inferred_tickers,
                retrieved_count=len(retrieved),
                retrieved_top_tickers=top_tickers,
                citation_count=len(latest.citations),
                citation_tickers=citation_tickers,
                pass_status=False,
                failure_reason="Incorrect inferred ticker",
            )

        if not retrieved:
            return SweepResult(
                ticker=ticker,
                inferred_tickers=inferred_tickers,
                retrieved_count=0,
                retrieved_top_tickers=top_tickers,
                citation_count=len(latest.citations),
                citation_tickers=citation_tickers,
                pass_status=False,
                failure_reason="No retrieved passages",
            )

        if not latest.citations:
            return SweepResult(
                ticker=ticker,
                inferred_tickers=inferred_tickers,
                retrieved_count=len(retrieved),
                retrieved_top_tickers=top_tickers,
                citation_count=0,
                citation_tickers=[],
                pass_status=False,
                failure_reason="No persisted citations",
            )

        non_matching = [value for value in citation_tickers if value and value != ticker]
        if non_matching:
            return SweepResult(
                ticker=ticker,
                inferred_tickers=inferred_tickers,
                retrieved_count=len(retrieved),
                retrieved_top_tickers=top_tickers,
                citation_count=len(latest.citations),
                citation_tickers=citation_tickers,
                pass_status=False,
                failure_reason=f"Non-matching citation tickers: {sorted(set(non_matching))}",
            )

        return SweepResult(
            ticker=ticker,
            inferred_tickers=inferred_tickers,
            retrieved_count=len(retrieved),
            retrieved_top_tickers=top_tickers,
            citation_count=len(latest.citations),
            citation_tickers=citation_tickers,
            pass_status=True,
            failure_reason=None,
        )


async def _main() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set.")
        return 2

    ingested_tickers = _distinct_tickers()
    results: list[SweepResult] = []

    for ticker in ingested_tickers:
        prompt = PROMPTS_BY_TICKER.get(ticker)
        if prompt is None:
            results.append(
                SweepResult(
                    ticker=ticker,
                    inferred_tickers=[],
                    retrieved_count=0,
                    retrieved_top_tickers=[],
                    citation_count=0,
                    citation_tickers=[],
                    pass_status=False,
                    failure_reason="No prompt configured for ticker",
                )
            )
            continue

        result = await _run_ticker_check(ticker, prompt)
        results.append(result)

    print(json.dumps([asdict(result) for result in results], indent=2))

    failures = [result for result in results if not result.pass_status]
    if failures:
        print(f"Sweep failures: {len(failures)}")
        return 1

    print(f"Sweep passed: {len(results)} tickers")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))