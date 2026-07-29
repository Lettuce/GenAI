from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.database.chats import CitationWrite, add_turn_with_citations
from app.database.models.chat_message import ChatMessage
from app.database.models.message_citation import MessageCitation


class _FakeSession:
    def __init__(self) -> None:
        self.added_messages: list[ChatMessage] = []
        self.added_citations: list[MessageCitation] = []

    def add(self, obj: object) -> None:
        if isinstance(obj, ChatMessage):
            self.added_messages.append(obj)
        elif isinstance(obj, MessageCitation):
            self.added_citations.append(obj)

    def add_all(self, items: list[object]) -> None:
        for item in items:
            self.add(item)

    def flush(self) -> None:
        for message in self.added_messages:
            if message.id is None:
                message.id = uuid.uuid4()
        for citation in self.added_citations:
            if citation.id is None:
                citation.id = uuid.uuid4()
            if citation.message_id is None and self.added_messages:
                citation.message_id = self.added_messages[-1].id

    def commit(self) -> None:
        self.flush()

    def refresh(self, obj: object) -> None:
        if isinstance(obj, ChatMessage) and obj.id is None:
            obj.id = uuid.uuid4()
        if isinstance(obj, ChatMessage) and obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)
        if isinstance(obj, MessageCitation) and obj.id is None:
            obj.id = uuid.uuid4()
        if isinstance(obj, MessageCitation) and obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)


def test_add_turn_with_citations_persists_assistant_citations() -> None:
    session = _FakeSession()
    thread_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    source_document_id = uuid.uuid4()

    user_message, assistant_message, citations = add_turn_with_citations(
        session,  # type: ignore[arg-type]
        thread_id=thread_id,
        user_content='What supports services growth?',
        assistant_content='Apple services growth is cited from filing content.',
        citations=[
            CitationWrite(
                chunk_id=chunk_id,
                source_document_id=source_document_id,
                quote='Services revenue increased year over year.',
                page_number=12,
            )
        ],
    )

    assert user_message.role == 'user'
    assert assistant_message.role == 'assistant'
    assert len(citations) == 1
    assert citations[0].chunk_id == str(chunk_id)
    assert citations[0].source_document_id == str(source_document_id)
