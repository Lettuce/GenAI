from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

from sqlalchemy.orm import Session

from app.chat.streaming import build_stub_response, iter_ai_sdk_data_stream_events
from app.database import chats


async def stream_stub_turn(
    *,
    db: Session,
    thread_id: uuid.UUID,
    user_text: str,
) -> AsyncGenerator[str, None]:
    assistant_text = build_stub_response(user_text)

    async for event in iter_ai_sdk_data_stream_events(assistant_text):
        yield event

    chats.add_turn_messages(
        db,
        thread_id=thread_id,
        user_content=user_text,
        assistant_content=assistant_text,
    )
