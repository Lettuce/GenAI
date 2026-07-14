from __future__ import annotations

import asyncio
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
