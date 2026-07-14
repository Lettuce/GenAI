from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.chat_message import ChatMessage
from app.database.models.chat_thread import ChatThread
from app.database.models.user import User


@dataclass
class PersistedThread:
    id: str
    title: str | None
    created_at: str


@dataclass
class PersistedMessage:
    id: str
    thread_id: str
    role: str
    content: str
    created_at: str


def ensure_user(db: Session, user_id: uuid.UUID, email: str | None) -> User:
    user = db.get(User, user_id)
    if user is not None:
        if email and user.email != email:
            user.email = email
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    fallback_email = email or f"{user_id}@local.invalid"
    user = User(id=user_id, email=fallback_email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_threads(db: Session, user_id: uuid.UUID) -> list[PersistedThread]:
    rows = db.execute(
        select(ChatThread)
        .where(ChatThread.user_id == user_id)
        .order_by(ChatThread.created_at.desc())
    ).scalars()
    return [
        PersistedThread(id=str(row.id), title=row.title, created_at=row.created_at.isoformat())
        for row in rows
    ]


def create_thread(db: Session, user_id: uuid.UUID, title: str | None = None) -> PersistedThread:
    thread = ChatThread(user_id=user_id, title=title)
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return PersistedThread(id=str(thread.id), title=thread.title, created_at=thread.created_at.isoformat())


def get_thread_for_user(db: Session, user_id: uuid.UUID, thread_id: uuid.UUID) -> ChatThread | None:
    return db.execute(
        select(ChatThread)
        .where(ChatThread.id == thread_id, ChatThread.user_id == user_id)
    ).scalar_one_or_none()


def get_thread_by_id(db: Session, thread_id: uuid.UUID) -> ChatThread | None:
    return db.execute(select(ChatThread).where(ChatThread.id == thread_id)).scalar_one_or_none()


def list_messages(db: Session, user_id: uuid.UUID, thread_id: uuid.UUID) -> list[PersistedMessage]:
    thread = get_thread_for_user(db, user_id, thread_id)
    if thread is None:
        return []

    rows = db.execute(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.asc())
    ).scalars()
    return [
        PersistedMessage(
            id=str(row.id),
            thread_id=str(row.thread_id),
            role=row.role,
            content=row.content,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


def add_message(db: Session, thread_id: uuid.UUID, role: str, content: str) -> PersistedMessage:
    message = ChatMessage(thread_id=thread_id, role=role, content=content)
    db.add(message)
    db.commit()
    db.refresh(message)
    return PersistedMessage(
        id=str(message.id),
        thread_id=str(message.thread_id),
        role=message.role,
        content=message.content,
        created_at=message.created_at.isoformat(),
    )


def add_turn_messages(
    db: Session,
    *,
    thread_id: uuid.UUID,
    user_content: str,
    assistant_content: str,
) -> tuple[PersistedMessage, PersistedMessage]:
    user_message = ChatMessage(thread_id=thread_id, role="user", content=user_content)
    assistant_message = ChatMessage(thread_id=thread_id, role="assistant", content=assistant_content)

    db.add(user_message)
    db.add(assistant_message)
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)

    return (
        PersistedMessage(
            id=str(user_message.id),
            thread_id=str(user_message.thread_id),
            role=user_message.role,
            content=user_message.content,
            created_at=user_message.created_at.isoformat(),
        ),
        PersistedMessage(
            id=str(assistant_message.id),
            thread_id=str(assistant_message.thread_id),
            role=assistant_message.role,
            content=assistant_message.content,
            created_at=assistant_message.created_at.isoformat(),
        ),
    )
