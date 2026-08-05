from __future__ import annotations

import uuid
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.assistant.outputs import GroundedAnswer, SourcePassage
from app.auth.dependencies import get_current_user
from app.database.models.chat_message import ChatMessage
from app.database.models.chat_thread import ChatThread
from app.database.models.message_citation import MessageCitation
from app.database.models.source_document import SourceDocument
from app.database.models.user import User
from app.database.session import get_db_session
from app.main import app


def test_stream_roundtrip_persists_and_returns_citations(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / 'chat-stream-citation-roundtrip.db'
    engine = create_engine(f'sqlite+pysqlite:///{db_path}', future=True)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)

    User.__table__.create(engine)
    SourceDocument.__table__.create(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE document_chunks (
                id CHAR(32) PRIMARY KEY,
                source_document_id CHAR(32) NOT NULL,
                content TEXT NOT NULL,
                embedding TEXT NULL,
                search_vector TEXT NULL,
                page_number INTEGER NULL,
                created_at DATETIME NULL
            )
            """
        )
    ChatThread.__table__.create(engine)
    ChatMessage.__table__.create(engine)
    MessageCitation.__table__.create(engine)

    user_id = uuid.uuid4()
    thread_id = uuid.uuid4()
    document_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    with session_factory() as session:
        session.add(User(id=user_id, email='phase7@example.com'))
        session.add(SourceDocument(id=document_id, company_name='Microsoft', filing_type='10-K', filing_year=2024))
        session.connection().exec_driver_sql(
            """
            INSERT INTO document_chunks (id, source_document_id, content, page_number)
            VALUES (?, ?, ?, ?)
            """,
            (chunk_id.hex, document_id.hex, 'Services revenue increased year over year.', 42),
        )
        session.add(ChatThread(id=thread_id, user_id=user_id, title='Citation roundtrip'))
        session.commit()

    def fake_retrieve_passages(_deps, _query: str) -> list[SourcePassage]:
        return [
            SourcePassage(
                chunk_id=str(chunk_id),
                document_id=str(document_id),
                content='Services revenue increased year over year.',
                page_number=42,
                ticker='MSFT',
                company_name='Microsoft',
                filing_type='10-K',
                filing_year=2024,
                filing_date=None,
                accession_number=None,
                source_url='https://example.com/msft-10k',
            )
        ]

    async def fake_answer(self, *, user_query: str, deps, retrieved_passages=None) -> GroundedAnswer:  # type: ignore[no-untyped-def]
        return GroundedAnswer(
            answer_text='Microsoft reported services growth backed by filings.',
            citations=[],
            insufficient_evidence=False,
            refusal_reason=None,
        )

    monkeypatch.setattr('app.chat.orchestrator.GroundedAssistantAgent.retrieve_passages', staticmethod(fake_retrieve_passages))
    monkeypatch.setattr('app.chat.orchestrator.GroundedAssistantAgent.answer', fake_answer)

    def override_get_current_user() -> dict[str, str]:
        return {'id': str(user_id), 'email': 'phase7@example.com'}

    def override_get_db_session() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db_session] = override_get_db_session

    try:
        client = TestClient(app)
        stream_response = client.post(
            '/chat/stream',
            json={
                'threadId': str(thread_id),
                'messages': [
                    {
                        'id': 'msg-1',
                        'role': 'user',
                        'parts': [{'type': 'text', 'text': 'What supports services growth?'}],
                    }
                ],
            },
        )
        assert stream_response.status_code == 200

        messages_response = client.get(f'/chat/threads/{thread_id}/messages')
        assert messages_response.status_code == 200

        payload = messages_response.json()
        assistant_payload = next(item for item in payload if item['role'] == 'assistant')
        assert len(assistant_payload['citations']) >= 1
        assert assistant_payload['citations'][0]['chunk_id'] == str(chunk_id)
        assert assistant_payload['citations'][0]['source_document_id'] == str(document_id)
    finally:
        app.dependency_overrides.clear()
