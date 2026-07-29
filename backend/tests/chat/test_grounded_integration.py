from __future__ import annotations

import asyncio
import os
import uuid

import pytest

from app.chat.orchestrator import stream_grounded_turn
from app.database import chats
from app.database.session import SessionLocal


@pytest.mark.integration
def test_grounded_stream_live_openai_supabase_roundtrip() -> None:
    if os.getenv("RUN_LIVE_GROUNDED_TEST") != "1":
        pytest.skip("Set RUN_LIVE_GROUNDED_TEST=1 to run live OpenAI+Supabase grounding integration test.")

    user_id = uuid.uuid4()
    test_email = f"phase6-integration-{user_id}@example.com"

    with SessionLocal() as db:
        chats.ensure_user(db, user_id=user_id, email=test_email)
        thread = chats.create_thread(db, user_id=user_id, title="Phase 6 grounded integration")
        thread_id = uuid.UUID(thread.id)

        async def _collect_events() -> list[str]:
            events: list[str] = []
            async for event in stream_grounded_turn(
                db=db,
                thread_id=thread_id,
                user_text="What sources support Apple services growth?",
                user_id=user_id,
            ):
                events.append(event)
            return events

        events = asyncio.run(_collect_events())

        persisted = chats.list_messages(db, user_id=user_id, thread_id=thread_id)

    assert events
    assert any('"type": "finish"' in event for event in events)
    assert len(persisted) >= 2
    assert persisted[-1].role == "assistant"
