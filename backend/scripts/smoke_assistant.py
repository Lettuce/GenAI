from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from pathlib import Path

import nest_asyncio


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.chat.orchestrator import stream_grounded_turn
from app.database import chats
from app.database.session import SessionLocal
from app.schemas.config import settings

nest_asyncio.apply()  # Allow nested asyncio.run() calls in Jupyter notebooks

logger = logging.getLogger("smoke_assistant")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )

USER_QUERIES = {
    "summary": "Summarize what this assistant currently does in one sentence.",
    "grounding": "What sources would you use to answer a question about Apple Services growth?",
    "limits": "What can this assistant not do yet?",
}


def _query_for(key: str) -> str:
    if key not in USER_QUERIES:
        valid_keys = ", ".join(USER_QUERIES.keys())
        raise ValueError(f"Unknown query key '{key}'. Use one of: {valid_keys}")
    return USER_QUERIES[key]


async def _run_once(query_key: str) -> None:
    user_text = _query_for(query_key)
    user_id = uuid.uuid4()

    logger.info("Starting assistant smoke run | query_key=%s", query_key)
    logger.info("Question text: %s", user_text)

    with SessionLocal() as db:
        logger.info("Creating temporary smoke user/thread")
        chats.ensure_user(db, user_id=user_id, email="smoke-assistant@example.com")
        thread = chats.create_thread(db, user_id=user_id, title=f"Smoke Assistant: {query_key}")
        thread_id = uuid.UUID(thread.id)
        logger.info("Thread created | thread_id=%s", thread.id)

        event_count = 0
        async for _ in stream_grounded_turn(db=db, thread_id=thread_id, user_text=user_text, user_id=user_id):
            event_count += 1
        logger.info("Stream completed | events=%d", event_count)

        persisted_messages = chats.list_messages(db, user_id=user_id, thread_id=thread_id)
        logger.info("Persisted messages fetched | count=%d", len(persisted_messages))

    print(f"Query key: {query_key}")
    print(f"Question: {user_text}")
    print("\nPersisted turn:")
    for message in persisted_messages[-2:]:
        print(f"- {message.role}: {message.content}")


async def _run_many_parallel(query_keys: list[str], max_parallel: int) -> None:
    logger.info("Parallel smoke checks started | total=%d max_parallel=%d", len(query_keys), max_parallel)
    semaphore = asyncio.Semaphore(max_parallel)

    async def _guarded_run(query_key: str) -> None:
        async with semaphore:
            await _run_once(query_key)

    await asyncio.gather(*[_guarded_run(query_key) for query_key in query_keys])
    logger.info("Parallel smoke checks finished")


def main() -> None:
    # Importing settings loads backend/.env and mirrors OPENAI_API_KEY for SDK clients.
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set. Check backend/.env and app/schemas/config.py settings.")

    logger.info("Config loaded | chat_model=%s", settings.openai_chat_model)

    # Toggle this for one-by-one vs parallel checks.
    run_parallel_checks = False

    # Single-run mode: set one key.
    query_key = "summary"

    # Parallel mode: set keys and cap concurrency.
    query_keys_for_parallel = ["summary", "grounding", "limits"]
    max_parallel = 2

    if run_parallel_checks:
        asyncio.run(_run_many_parallel(query_keys_for_parallel, max_parallel))
    else:
        asyncio.run(_run_once(query_key))


if __name__ == "__main__":
    main()
