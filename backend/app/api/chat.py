from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.chat.orchestrator import stream_stub_turn
from app.chat.messages import extract_last_user_text
from app.database import chats
from app.database.session import get_db_session

router = APIRouter(prefix="/chat", tags=["chat"])


class ThreadResponse(BaseModel):
    id: str
    title: str | None
    created_at: str


class MessageResponse(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str
    created_at: str


class CreateThreadRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ChatStreamRequest(BaseModel):
    thread_id: str = Field(alias="threadId")
    messages: list[dict[str, Any]]


def _parse_user_id(raw_user_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw_user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated user id is not a valid UUID",
        ) from exc


def _parse_thread_id(raw_thread_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw_thread_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="threadId must be a valid UUID",
        ) from exc


@router.get("/threads", response_model=list[ThreadResponse])
async def get_threads(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[ThreadResponse]:
    user_id = _parse_user_id(current_user["id"])
    chats.ensure_user(db, user_id=user_id, email=current_user.get("email"))
    return [ThreadResponse(**thread.__dict__) for thread in chats.list_threads(db, user_id=user_id)]


@router.post("/threads", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
async def post_thread(
    payload: CreateThreadRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> ThreadResponse:
    user_id = _parse_user_id(current_user["id"])
    chats.ensure_user(db, user_id=user_id, email=current_user.get("email"))
    thread = chats.create_thread(db, user_id=user_id, title=payload.title)
    return ThreadResponse(**thread.__dict__)


@router.get("/threads/{thread_id}/messages", response_model=list[MessageResponse])
async def get_thread_messages(
    thread_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[MessageResponse]:
    user_id = _parse_user_id(current_user["id"])
    parsed_thread_id = _parse_thread_id(thread_id)
    thread = chats.get_thread_by_id(db, thread_id=parsed_thread_id)
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    if thread.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    return [
        MessageResponse(**message.__dict__)
        for message in chats.list_messages(db, user_id=user_id, thread_id=parsed_thread_id)
    ]


@router.post("/stream")
async def post_chat_stream(
    payload: ChatStreamRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> StreamingResponse:
    user_id = _parse_user_id(current_user["id"])
    thread_id = _parse_thread_id(payload.thread_id)
    chats.ensure_user(db, user_id=user_id, email=current_user.get("email"))

    thread = chats.get_thread_by_id(db, thread_id=thread_id)
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    if thread.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    user_text = extract_last_user_text(payload.messages)
    if not user_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No user message content found")

    async def stream_text() -> AsyncGenerator[str, None]:
        async for chunk in stream_stub_turn(db=db, thread_id=thread_id, user_text=user_text):
            yield chunk

    return StreamingResponse(stream_text(), media_type="text/plain; charset=utf-8")
