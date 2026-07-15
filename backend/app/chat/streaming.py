from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator


def build_stub_response(user_text: str) -> str:
    if not user_text:
        return "Stub assistant response: no user text was provided in this turn."

    snippet = user_text[:180]
    return (
        "Stub assistant response: I received your message and streaming is wired end-to-end. "
        f"Echo: {snippet}"
    )


async def iter_text_chunks(text: str, *, delay_seconds: float = 0.03) -> AsyncGenerator[str, None]:
    words = text.split(" ")
    for index, word in enumerate(words):
        chunk = word if index == len(words) - 1 else f"{word} "
        yield chunk
        await asyncio.sleep(delay_seconds)


def _encode_sse_data(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def iter_ai_sdk_data_stream_events(
    text: str,
    *,
    message_id: str | None = None,
    text_part_id: str | None = None,
) -> AsyncGenerator[str, None]:
    next_message_id = message_id or str(uuid.uuid4())
    next_text_part_id = text_part_id or str(uuid.uuid4())

    yield _encode_sse_data({"type": "start", "messageId": next_message_id})
    yield _encode_sse_data({"type": "text-start", "id": next_text_part_id})

    async for chunk in iter_text_chunks(text):
        yield _encode_sse_data({"type": "text-delta", "id": next_text_part_id, "delta": chunk})

    yield _encode_sse_data({"type": "text-end", "id": next_text_part_id})
    yield _encode_sse_data({"type": "finish", "finishReason": "stop"})
