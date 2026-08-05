from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.chat.orchestrator import stream_grounded_turn
from app.chat.messages import extract_last_user_text
from app.chat.streaming import iter_ai_sdk_data_stream_events
from app.database import chats
from app.database.session import get_db_session

router = APIRouter(prefix="/chat", tags=["chat"])


class ThreadResponse(BaseModel):
    id: str
    title: str | None
    created_at: str


class NeighboringChunkResponse(BaseModel):
    relation: str
    excerpt: str
    page_number: int | None


class CitationResponse(BaseModel):
    chunk_id: str
    source_document_id: str
    quote: str | None
    page_number: int | None
    excerpt: str | None
    ticker: str | None
    company_name: str | None
    filing_type: str | None
    filing_year: int | None
    filing_date: str | None
    source_url: str | None
    neighboring_chunks: list[NeighboringChunkResponse] = Field(default_factory=list)


class MessageResponse(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str
    created_at: str
    citations: list[CitationResponse] = Field(default_factory=list)


class CreateThreadRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class UpdateThreadRequest(BaseModel):
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


@router.patch("/threads/{thread_id}", response_model=ThreadResponse)
async def patch_thread(
    thread_id: str,
    payload: UpdateThreadRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> ThreadResponse:
    user_id = _parse_user_id(current_user["id"])
    parsed_thread_id = _parse_thread_id(thread_id)

    updated = chats.update_thread_title(
        db,
        user_id=user_id,
        thread_id=parsed_thread_id,
        title=payload.title,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    return ThreadResponse(**updated.__dict__)


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> None:
    user_id = _parse_user_id(current_user["id"])
    parsed_thread_id = _parse_thread_id(thread_id)

    deleted = chats.delete_thread(db, user_id=user_id, thread_id=parsed_thread_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")


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
        MessageResponse(
            id=message.id,
            thread_id=message.thread_id,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
                citations=[
                    CitationResponse(
                        **{
                            **citation.__dict__,
                            "neighboring_chunks": [chunk.__dict__ for chunk in citation.neighboring_chunks],
                        }
                    )
                    for citation in message.citations
                ],
        )
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
        try:
            async for chunk in stream_grounded_turn(
                db=db,
                thread_id=thread_id,
                user_text=user_text,
                user_id=user_id,
            ):
                yield chunk
        except Exception:
            fallback_text = (
                "Analyzing\n"
                f"- {user_text}\n\n"
                "Searching\n"
                "- Retrieval failed due to a temporary backend issue\n\n"
                "Reading\n"
                "- No passage excerpts available\n\n"
                "Verifying\n"
                "- Verification could not complete because the backend request failed\n\n"
                "Answering\n"
                "I hit a temporary backend issue while processing this query. Please retry."
            )
            async for event in iter_ai_sdk_data_stream_events(fallback_text):
                yield event

    return StreamingResponse(
        stream_text(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "x-vercel-ai-ui-message-stream": "v1",
        },
    )
