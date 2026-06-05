"""FastAPI routes for chat threads and stubbed streaming."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.auth.dependencies import CurrentUser, get_access_token, get_current_user
from app.chat.messages import extract_last_user_message
from app.chat.streaming import stream_stub_and_persist
from app.database.chats import (
    create_thread,
    list_threads,
    load_messages,
    require_thread_access,
)
from app.database.supabase import create_user_client
from app.database.users import ensure_user
from app.schemas.chat import (
    CreateThreadRequest,
    MessageHistoryResponse,
    StreamRequest,
    ThreadListResponse,
    ThreadResponse,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/threads")
async def get_threads(
    user: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
) -> ThreadListResponse:
    await ensure_user(user)
    client = await create_user_client(access_token)
    threads = await list_threads(client, user)
    return ThreadListResponse(threads=threads)


@router.post("/threads")
async def post_thread(
    body: CreateThreadRequest,
    user: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
) -> ThreadResponse:
    await ensure_user(user)
    client = await create_user_client(access_token)
    return await create_thread(client, user, title=body.title)


@router.get("/threads/{thread_id}/messages")
async def get_thread_messages(
    thread_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
) -> MessageHistoryResponse:
    await require_thread_access(thread_id, user)
    client = await create_user_client(access_token)
    messages = await load_messages(client, thread_id)
    return MessageHistoryResponse(messages=messages)


@router.post("/stream")
async def post_stream(
    body: StreamRequest,
    user: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
) -> StreamingResponse:
    await ensure_user(user)
    thread = await require_thread_access(body.thread_id, user)
    user_message = extract_last_user_message(body.messages)
    client = await create_user_client(access_token)

    return StreamingResponse(
        stream_stub_and_persist(
            client=client,
            thread_id=body.thread_id,
            user_message=user_message,
            thread_title=thread.title,
        ),
        media_type="text/event-stream",
    )
