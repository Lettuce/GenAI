"""AI SDK-compatible SSE streaming for stubbed assistant replies."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from supabase import AsyncClient

from app.database.chats import append_turn_messages
from app.schemas.chat import UIMessage

STUB_REPLY = (
    "This is a stubbed response. Real retrieval and citations arrive in Phase 6."
)


def _sse_event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


async def _stub_text_events(
    text: str,
    *,
    message_id: str,
) -> AsyncIterator[str]:
    yield _sse_event({"type": "text-start", "id": message_id})

    for word in text.split(" "):
        yield _sse_event({"type": "text-delta", "id": message_id, "delta": f"{word} "})

    yield _sse_event({"type": "text-end", "id": message_id})


async def stream_stub_and_persist(
    *,
    client: AsyncClient,
    thread_id: uuid.UUID,
    user_message: UIMessage,
    thread_title: str,
    assistant_text: str = STUB_REPLY,
) -> AsyncIterator[str]:
    message_id = str(uuid.uuid4())

    try:
        async for event in _stub_text_events(assistant_text, message_id=message_id):
            yield event
    finally:
        await append_turn_messages(
            client,
            thread_id=thread_id,
            user_message=user_message,
            assistant_text=assistant_text,
            thread_title=thread_title,
        )