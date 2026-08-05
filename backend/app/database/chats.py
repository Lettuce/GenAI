from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models.chat_message import ChatMessage
from app.database.models.document_chunk import DocumentChunk
from app.database.models.message_citation import MessageCitation
from app.database.models.chat_thread import ChatThread
from app.database.models.source_document import SourceDocument
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
    citations: list["PersistedMessageCitation"] = field(default_factory=list)


@dataclass
class PersistedMessageCitation:
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
    neighboring_chunks: list["PersistedNeighborChunk"] = field(default_factory=list)


@dataclass
class PersistedNeighborChunk:
    relation: str
    excerpt: str
    page_number: int | None


@dataclass
class CitationWrite:
    chunk_id: uuid.UUID
    source_document_id: uuid.UUID
    quote: str | None = None
    page_number: int | None = None


@dataclass
class PersistedCitation:
    id: str
    message_id: str
    chunk_id: str
    source_document_id: str
    quote: str | None
    page_number: int | None
    created_at: str


_AUTO_TITLE_PLACEHOLDERS = {"new chat", "thread"}


def _ensure_message_citations_table(db: Session) -> None:
    bind = db.get_bind()
    MessageCitation.__table__.create(bind=bind, checkfirst=True)


def _summarize_thread_title(user_content: str, *, max_length: int = 80) -> str:
    cleaned = " ".join(user_content.split()).strip()
    if not cleaned:
        return "New Chat"

    if len(cleaned) <= max_length:
        return cleaned

    return f"{cleaned[: max_length - 1].rstrip()}..."


def _set_thread_title_if_missing(db: Session, *, thread_id: uuid.UUID, user_content: str) -> None:
    thread = get_thread_by_id(db, thread_id=thread_id)
    if thread is None:
        return

    existing_title = (thread.title or "").strip()
    if existing_title and existing_title.lower() not in _AUTO_TITLE_PLACEHOLDERS:
        return

    thread.title = _summarize_thread_title(user_content)
    db.add(thread)


def update_thread_title(
    db: Session,
    *,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
    title: str | None,
) -> PersistedThread | None:
    thread = get_thread_for_user(db, user_id=user_id, thread_id=thread_id)
    if thread is None:
        return None

    normalized_title = (title or "").strip()
    thread.title = normalized_title or None
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return PersistedThread(id=str(thread.id), title=thread.title, created_at=thread.created_at.isoformat())


def delete_thread(db: Session, *, user_id: uuid.UUID, thread_id: uuid.UUID) -> bool:
    _ensure_message_citations_table(db)

    thread = get_thread_for_user(db, user_id=user_id, thread_id=thread_id)
    if thread is None:
        return False

    message_ids = db.execute(
        select(ChatMessage.id).where(ChatMessage.thread_id == thread_id)
    ).scalars().all()

    if message_ids:
        db.execute(
            sa_delete(MessageCitation).where(MessageCitation.message_id.in_(message_ids))
        )

    db.execute(sa_delete(ChatMessage).where(ChatMessage.thread_id == thread_id))
    db.execute(
        sa_delete(ChatThread).where(
            ChatThread.id == thread_id,
            ChatThread.user_id == user_id,
        )
    )
    db.commit()
    return True


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
    messages = [
        PersistedMessage(
            id=str(row.id),
            thread_id=str(row.thread_id),
            role=row.role,
            content=row.content,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]

    if not messages:
        return messages

    message_ids = [uuid.UUID(message.id) for message in messages]
    citations_by_message_id: dict[uuid.UUID, list[PersistedMessageCitation]] = {}

    try:
        _ensure_message_citations_table(db)

        chunk_rows = db.execute(
            select(
                DocumentChunk.id,
                DocumentChunk.source_document_id,
                DocumentChunk.content,
                DocumentChunk.page_number,
                DocumentChunk.created_at,
            )
        ).all()

        ordered_chunks_by_document_id: dict[uuid.UUID, list[tuple[uuid.UUID, str, int | None]]] = {}
        chunk_position_by_id: dict[uuid.UUID, tuple[uuid.UUID, int]] = {}

        grouped_chunks: dict[uuid.UUID, list[tuple[uuid.UUID, str, int | None, object | None]]] = {}
        for chunk_id, source_document_id, content, page_number, created_at in chunk_rows:
            grouped_chunks.setdefault(source_document_id, []).append((chunk_id, content, page_number, created_at))

        for source_document_id, raw_chunks in grouped_chunks.items():
            ordered_raw_chunks = sorted(
                raw_chunks,
                key=lambda row: (
                    row[2] if row[2] is not None else 1_000_000_000,
                    row[3].isoformat() if row[3] is not None else '',
                    str(row[0]),
                ),
            )
            ordered = [(chunk_id, content, page_number) for chunk_id, content, page_number, _ in ordered_raw_chunks]
            ordered_chunks_by_document_id[source_document_id] = ordered
            for index, (chunk_id, _, _) in enumerate(ordered):
                chunk_position_by_id[chunk_id] = (source_document_id, index)

        citation_rows = db.execute(
            select(
                MessageCitation.message_id,
                MessageCitation.chunk_id,
                MessageCitation.source_document_id,
                MessageCitation.quote,
                MessageCitation.page_number,
                DocumentChunk.content,
                SourceDocument.ticker,
                SourceDocument.company_name,
                SourceDocument.filing_type,
                SourceDocument.filing_year,
                SourceDocument.filing_date,
                SourceDocument.source_url,
            )
            .join(DocumentChunk, DocumentChunk.id == MessageCitation.chunk_id)
            .join(SourceDocument, SourceDocument.id == MessageCitation.source_document_id)
            .where(MessageCitation.message_id.in_(message_ids))
            .order_by(MessageCitation.created_at.asc())
        ).all()

        for row in citation_rows:
            filing_date_iso = row[10].isoformat() if row[10] is not None else None
            neighboring_chunks: list[PersistedNeighborChunk] = []
            chunk_position = chunk_position_by_id.get(row[1])
            if chunk_position is not None:
                source_document_id, chunk_index = chunk_position
                ordered_chunks = ordered_chunks_by_document_id.get(source_document_id, [])
                previous_chunk = ordered_chunks[chunk_index - 1] if chunk_index - 1 >= 0 else None
                next_chunk = ordered_chunks[chunk_index + 1] if chunk_index + 1 < len(ordered_chunks) else None
                if previous_chunk is not None:
                    neighboring_chunks.append(
                        PersistedNeighborChunk(
                            relation="previous",
                            excerpt=previous_chunk[1],
                            page_number=previous_chunk[2],
                        )
                    )
                if next_chunk is not None:
                    neighboring_chunks.append(
                        PersistedNeighborChunk(
                            relation="next",
                            excerpt=next_chunk[1],
                            page_number=next_chunk[2],
                        )
                    )

            citation = PersistedMessageCitation(
                chunk_id=str(row[1]),
                source_document_id=str(row[2]),
                quote=row[3],
                page_number=row[4],
                excerpt=row[5],
                ticker=row[6],
                company_name=row[7],
                filing_type=row[8],
                filing_year=row[9],
                filing_date=filing_date_iso,
                source_url=row[11],
                neighboring_chunks=neighboring_chunks,
            )
            citations_by_message_id.setdefault(row[0], []).append(citation)
    except SQLAlchemyError:
        db.rollback()
        citations_by_message_id = {}

    for message in messages:
        parsed_message_id = uuid.UUID(message.id)
        message.citations = citations_by_message_id.get(parsed_message_id, [])

    return messages


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
    _set_thread_title_if_missing(db, thread_id=thread_id, user_content=user_content)

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


def add_turn_with_citations(
    db: Session,
    *,
    thread_id: uuid.UUID,
    user_content: str,
    assistant_content: str,
    citations: list[CitationWrite],
) -> tuple[PersistedMessage, PersistedMessage, list[PersistedCitation]]:
    _set_thread_title_if_missing(db, thread_id=thread_id, user_content=user_content)

    user_message = ChatMessage(thread_id=thread_id, role="user", content=user_content)
    assistant_message = ChatMessage(thread_id=thread_id, role="assistant", content=assistant_content)

    db.add(user_message)
    db.add(assistant_message)
    db.flush()

    citation_rows: list[MessageCitation] = []
    for citation in citations:
        citation_rows.append(
            MessageCitation(
                message_id=assistant_message.id,
                chunk_id=citation.chunk_id,
                source_document_id=citation.source_document_id,
                quote=citation.quote,
                page_number=citation.page_number,
            )
        )

    if citation_rows:
        db.add_all(citation_rows)

    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)
    for citation_row in citation_rows:
        db.refresh(citation_row)

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
        [
            PersistedCitation(
                id=str(citation_row.id),
                message_id=str(citation_row.message_id),
                chunk_id=str(citation_row.chunk_id),
                source_document_id=str(citation_row.source_document_id),
                quote=citation_row.quote,
                page_number=citation_row.page_number,
                created_at=citation_row.created_at.isoformat(),
            )
            for citation_row in citation_rows
        ],
    )


def add_message_citations(
    db: Session,
    *,
    message_id: uuid.UUID,
    citations: list[CitationWrite],
) -> list[PersistedCitation]:
    if not citations:
        return []

    _ensure_message_citations_table(db)

    unique_chunk_ids = list({citation.chunk_id for citation in citations})
    chunk_rows = db.execute(
        select(DocumentChunk.id, DocumentChunk.source_document_id).where(DocumentChunk.id.in_(unique_chunk_ids))
    ).all()
    source_document_by_chunk_id = {row[0]: row[1] for row in chunk_rows}

    citation_rows: list[MessageCitation] = []
    seen_keys: set[tuple[uuid.UUID, uuid.UUID, int | None, str | None]] = set()

    for citation in citations:
        source_document_id = source_document_by_chunk_id.get(citation.chunk_id)
        if source_document_id is None:
            continue

        dedupe_key = (
            citation.chunk_id,
            source_document_id,
            citation.page_number,
            citation.quote,
        )
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        citation_rows.append(
            MessageCitation(
                message_id=message_id,
                chunk_id=citation.chunk_id,
                source_document_id=source_document_id,
                quote=citation.quote,
                page_number=citation.page_number,
            )
        )

    if not citation_rows:
        return []

    db.add_all(citation_rows)
    db.commit()
    for citation_row in citation_rows:
        db.refresh(citation_row)

    return [
        PersistedCitation(
            id=str(citation_row.id),
            message_id=str(citation_row.message_id),
            chunk_id=str(citation_row.chunk_id),
            source_document_id=str(citation_row.source_document_id),
            quote=citation_row.quote,
            page_number=citation_row.page_number,
            created_at=citation_row.created_at.isoformat(),
        )
        for citation_row in citation_rows
    ]
