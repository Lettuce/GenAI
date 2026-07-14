from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

from sqlalchemy.orm import Session

from app.chat.streaming import build_stub_response, iter_text_chunks
from app.database import chats


async def stream_stub_turn(
    *,
    db: Session,
    thread_id: uuid.UUID,
    user_text: str,
) -> AsyncGenerator[str, None]:
    assistant_text = build_stub_response(user_text)
    chunks: list[str] = []

    async for chunk in iter_text_chunks(assistant_text):
        chunks.append(chunk)
        yield chunk

    final_assistant_text = "".join(chunks)
    chats.add_turn_messages(
        db,
        thread_id=thread_id,
        user_content=user_text,
        assistant_content=final_assistant_text,
    )
