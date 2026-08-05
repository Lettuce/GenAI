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


def test_create_prompt_citations_and_delete_flow(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / 'chat-amazon-flow.db'
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
    with session_factory() as session:
        session.add(User(id=user_id, email='phase7@example.com'))

        docs = [
            (uuid.uuid4(), 'Amazon', 2022, 'North America remained the largest segment while AWS expanded operating contribution.', 18),
            (uuid.uuid4(), 'Amazon', 2023, 'International mix improved and advertising accelerated relative to online stores.', 24),
            (uuid.uuid4(), 'Amazon', 2024, 'AWS and advertising gained mix share while first-party online stores moderated.', 31),
        ]

        chunk_rows: list[tuple[uuid.UUID, uuid.UUID, str, int]] = []
        for document_id, company_name, filing_year, _, _ in docs:
            session.add(
                SourceDocument(
                    id=document_id,
                    ticker='AMZN',
                    company_name=company_name,
                    filing_type='10-K',
                    filing_year=filing_year,
                    source_url=f'https://example.com/amzn-{filing_year}',
                )
            )

        for document_id, _, _, content, page_number in docs:
            chunk_id = uuid.uuid4()
            chunk_rows.append((chunk_id, document_id, content, page_number))
            session.connection().exec_driver_sql(
                """
                INSERT INTO document_chunks (id, source_document_id, content, page_number)
                VALUES (?, ?, ?, ?)
                """,
                (chunk_id.hex, document_id.hex, content, page_number),
            )

        session.commit()

    def fake_retrieve_passages(_deps, _query: str) -> list[SourcePassage]:
        with session_factory() as session:
            rows = session.connection().exec_driver_sql(
                """
                SELECT dc.id, dc.source_document_id, dc.content, dc.page_number, sd.ticker, sd.company_name, sd.filing_type, sd.filing_year, sd.source_url
                FROM document_chunks dc
                JOIN source_documents sd ON sd.id = dc.source_document_id
                ORDER BY sd.filing_year ASC
                """
            ).fetchall()

        passages: list[SourcePassage] = []
        for row in rows:
            passages.append(
                SourcePassage(
                    chunk_id=str(uuid.UUID(hex=row[0])),
                    document_id=str(uuid.UUID(hex=row[1])),
                    content=row[2],
                    page_number=row[3],
                    ticker=row[4],
                    company_name=row[5],
                    filing_type=row[6],
                    filing_year=row[7],
                    filing_date=None,
                    accession_number=None,
                    source_url=row[8],
                )
            )
        return passages

    async def fake_answer(self, *, user_query: str, deps, retrieved_passages=None) -> GroundedAnswer:  # type: ignore[no-untyped-def]
        return GroundedAnswer(
            answer_text=(
                "Amazon's revenue mix shifted over the last three fiscal years: "
                "AWS and advertising gained share while first-party online stores contributed less mix than earlier years."
            ),
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

        create_response = client.post('/chat/threads', json={'title': 'Amazon revenue mix'})
        assert create_response.status_code == 201
        thread_id = create_response.json()['id']

        prompt = "How was Amazon's revenue mix shifted over the last three fiscal years?"
        stream_response = client.post(
            '/chat/stream',
            json={
                'threadId': thread_id,
                'messages': [
                    {
                        'id': 'msg-1',
                        'role': 'user',
                        'parts': [{'type': 'text', 'text': prompt}],
                    }
                ],
            },
        )
        assert stream_response.status_code == 200

        messages_response = client.get(f'/chat/threads/{thread_id}/messages')
        assert messages_response.status_code == 200
        messages_payload = messages_response.json()

        assistant_message = next(item for item in messages_payload if item['role'] == 'assistant')
        citations = assistant_message['citations']
        assert len(citations) == 3
        assert all(citation['ticker'] == 'AMZN' for citation in citations)
        assert all(citation['filing_type'] == '10-K' for citation in citations)

        delete_response = client.delete(f'/chat/threads/{thread_id}')
        assert delete_response.status_code == 204

        list_response = client.get('/chat/threads')
        assert list_response.status_code == 200
        assert all(item['id'] != thread_id for item in list_response.json())
    finally:
        app.dependency_overrides.clear()
