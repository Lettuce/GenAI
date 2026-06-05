"""Chat thread and message persistence via Supabase."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from supabase import AsyncClient

from app.auth.dependencies import CurrentUser
from app.chat.messages import (
    DEFAULT_THREAD_TITLE,
    build_assistant_message,
    row_to_ui_message,
    ui_message_to_insert,
)
from app.database.supabase import get_service_role_client
from app.schemas.chat import ThreadResponse, UIMessage, thread_row_to_response


@dataclass(frozen=True, slots=True)
class ThreadRow:
    id: uuid.UUID
    user_id: uuid.UUID
    title: str


async def require_thread_access(thread_id: uuid.UUID, user: CurrentUser) -> ThreadRow:
    client = await get_service_role_client()
    response = await (
        client.table("chat_threads")
        .select("id,user_id,title")
        .eq("id", str(thread_id))
        .maybe_single()
        .execute()
    )

    if response.data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found",
        )

    row = response.data
    owner_id = uuid.UUID(str(row["user_id"]))
    if owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    return ThreadRow(
        id=uuid.UUID(str(row["id"])),
        user_id=owner_id,
        title=row["title"],
    )


async def list_threads(client: AsyncClient, user: CurrentUser) -> list[ThreadResponse]:
    response = await (
        client.table("chat_threads")
        .select("id,title,created_at,updated_at")
        .eq("user_id", str(user.id))
        .order("updated_at", desc=True)
        .execute()
    )
    return [thread_row_to_response(row) for row in response.data]


async def create_thread(
    client: AsyncClient,
    user: CurrentUser,
    *,
    title: str | None = None,
) -> ThreadResponse:
    thread_id = uuid.uuid4()
    response = await (
        client.table("chat_threads")
        .insert(
            {
                "id": str(thread_id),
                "user_id": str(user.id),
                "title": title or DEFAULT_THREAD_TITLE,
            }
        )
        .select("id,title,created_at,updated_at")
        .single()
        .execute()
    )
    return thread_row_to_response(response.data)


async def load_messages(client: AsyncClient, thread_id: uuid.UUID) -> list[UIMessage]:
    response = await (
        client.table("chat_messages")
        .select("id,role,content,parts,sequence")
        .eq("thread_id", str(thread_id))
        .order("sequence")
        .execute()
    )
    return [row_to_ui_message(row) for row in response.data]


async def get_next_sequence(client: AsyncClient, thread_id: uuid.UUID) -> int:
    response = await (
        client.table("chat_messages")
        .select("sequence")
        .eq("thread_id", str(thread_id))
        .order("sequence", desc=True)
        .limit(1)
        .execute()
    )
    if not response.data:
        return 0
    return int(response.data[0]["sequence"]) + 1


async def append_turn_messages(
    client: AsyncClient,
    *,
    thread_id: uuid.UUID,
    user_message: UIMessage,
    assistant_text: str,
    thread_title: str,
) -> None:
    next_sequence = await get_next_sequence(client, thread_id)
    assistant_message = build_assistant_message(assistant_text)
    rows = [
        ui_message_to_insert(
            user_message,
            thread_id=thread_id,
            sequence=next_sequence,
        ),
        ui_message_to_insert(
            assistant_message,
            thread_id=thread_id,
            sequence=next_sequence + 1,
        ),
    ]
    await client.table("chat_messages").insert(rows).execute()

    updates: dict[str, Any] = {"updated_at": datetime.now(UTC).isoformat()}
    if thread_title == DEFAULT_THREAD_TITLE:
        from app.chat.messages import title_from_user_message

        updates["title"] = title_from_user_message(user_message)

    await (
        client.table("chat_threads")
        .update(updates)
        .eq("id", str(thread_id))
        .execute()
    )
