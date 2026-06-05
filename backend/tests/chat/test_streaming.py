import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.chat.streaming import STUB_REPLY, stream_stub_and_persist
from app.schemas.chat import MessagePart, UIMessage


@pytest.mark.anyio
async def test_stream_stub_emits_ai_sdk_sse_events() -> None:
    events: list[str] = []
    user_message = UIMessage(
        role="user",
        parts=[MessagePart(type="text", text="Hello")],
    )

    with patch(
        "app.chat.streaming.append_turn_messages",
        AsyncMock(),
    ):
        async for event in stream_stub_and_persist(
            client=MagicMock(),
            thread_id=uuid.uuid4(),
            user_message=user_message,
            thread_title="New chat",
            assistant_text="One two",
        ):
            events.append(event)

    assert events[0].startswith('data: {"type":"text-start"')
    assert any('"type":"text-delta"' in event for event in events)
    assert events[-1].startswith('data: {"type":"text-end"')
    assert all(event.endswith("\n\n") for event in events)


@pytest.mark.anyio
async def test_stream_stub_persists_after_completion() -> None:
    user_message = UIMessage(
        role="user",
        parts=[MessagePart(type="text", text="Hello")],
    )
    mock_append = AsyncMock()

    with patch("app.chat.streaming.append_turn_messages", mock_append):
        async for _ in stream_stub_and_persist(
            client=MagicMock(),
            thread_id=uuid.uuid4(),
            user_message=user_message,
            thread_title="New chat",
        ):
            pass

    mock_append.assert_awaited_once()
    assert mock_append.await_args.kwargs["assistant_text"] == STUB_REPLY
