from __future__ import annotations

import asyncio
import json

from app.chat.streaming import iter_ai_sdk_data_stream_events


def test_iter_ai_sdk_data_stream_events_emits_required_chunks() -> None:
    async def collect() -> list[str]:
        events: list[str] = []
        async for event in iter_ai_sdk_data_stream_events("Hello world"):
            events.append(event)
        return events

    events = asyncio.run(collect())

    assert events[0].startswith("data: ")
    payloads = [json.loads(event.removeprefix("data: ").strip()) for event in events]

    assert payloads[0]["type"] == "start"
    assert payloads[1]["type"] == "text-start"
    assert any(part["type"] == "text-delta" for part in payloads)
    assert payloads[-2]["type"] == "text-end"
    assert payloads[-1]["type"] == "finish"
