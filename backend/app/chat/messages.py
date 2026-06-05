"""Convert between AI SDK UI messages and chat_messages rows."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status

from app.database.models.message_role import MessageRole
from app.schemas.chat import MessagePart, UIMessage

DEFAULT_THREAD_TITLE = "New chat"
MAX_TITLE_LENGTH = 255


def text_from_parts(parts: list[MessagePart]) -> str:
    return "".join(part.text for part in parts if part.type == "text")


def extract_last_user_message(messages: list[UIMessage]) -> UIMessage:
    for message in reversed(messages):
        if message.role == "user":
            return message
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="Request must include at least one user message",
    )


def ui_message_to_insert(
    message: UIMessage,
    *,
    thread_id: uuid.UUID,
    sequence: int,
    message_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    parts = [part.model_dump() for part in message.parts]
    return {
        "id": str(message_id or uuid.uuid4()),
        "thread_id": str(thread_id),
        "role": MessageRole(message.role).value,
        "content": text_from_parts(message.parts) or None,
        "parts": parts,
        "sequence": sequence,
    }


def row_to_ui_message(row: dict[str, Any]) -> UIMessage:
    raw_parts = row.get("parts") or []
    parts = [MessagePart.model_validate(part) for part in raw_parts]
    if not parts and row.get("content"):
        parts = [MessagePart(type="text", text=row["content"])]

    return UIMessage(
        id=str(row["id"]),
        role=row["role"],
        parts=parts,
    )


def build_assistant_message(text: str, *, message_id: uuid.UUID | None = None) -> UIMessage:
    return UIMessage(
        id=str(message_id or uuid.uuid4()),
        role="assistant",
        parts=[MessagePart(type="text", text=text)],
    )


def title_from_user_message(message: UIMessage) -> str:
    text = text_from_parts(message.parts).strip()
    if not text:
        return DEFAULT_THREAD_TITLE
    if len(text) <= MAX_TITLE_LENGTH:
        return text
    return text[: MAX_TITLE_LENGTH - 3] + "..."
