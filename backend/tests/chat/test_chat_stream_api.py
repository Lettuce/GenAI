from __future__ import annotations

import json
import uuid
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.auth.dependencies import get_current_user
from app.database.models.chat_message import ChatMessage
from app.database.models.chat_thread import ChatThread
from app.database.models.message_citation import MessageCitation
from app.database.models.source_document import SourceDocument
from app.database.models.user import User
from app.database.session import get_db_session
from app.main import app


def test_stream_endpoint_accepts_ui_messages_and_persists_turn(tmp_path) -> None:
    db_path = tmp_path / 'chat-test.db'
    engine = create_engine(f'sqlite+pysqlite:///{db_path}', future=True)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)

    User.__table__.create(engine)
    ChatThread.__table__.create(engine)
    ChatMessage.__table__.create(engine)

    user_id = uuid.uuid4()
    thread_id = uuid.uuid4()

    with session_factory() as session:
        session.add(User(id=user_id, email='phase3@example.com'))
        session.add(ChatThread(id=thread_id, user_id=user_id, title='Phase 3'))
        session.commit()

    def override_get_current_user() -> dict[str, str]:
        return {'id': str(user_id), 'email': 'phase3@example.com'}

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
        response = client.post(
            '/chat/stream',
            json={
                'threadId': str(thread_id),
                'messages': [
                    {
                        'id': 'msg-1',
                        'role': 'user',
                        'parts': [{'type': 'text', 'text': 'Check wire format compatibility.'}],
                    }
                ],
            },
        )

        assert response.status_code == 200
        assert response.headers.get('x-vercel-ai-ui-message-stream') == 'v1'
        assert response.headers.get('content-type', '').startswith('text/event-stream')

        chunks = [chunk for chunk in response.text.split('\n\n') if chunk.strip()]
        payloads = [json.loads(chunk.removeprefix('data: ').strip()) for chunk in chunks if chunk.startswith('data: ')]

        assert payloads[0]['type'] == 'start'
        assert payloads[1]['type'] == 'text-start'
        assert any(part['type'] == 'text-delta' for part in payloads)
        assert payloads[-2]['type'] == 'text-end'
        assert payloads[-1]['type'] == 'finish'

        with session_factory() as session:
            persisted = session.execute(
                select(ChatMessage).where(ChatMessage.thread_id == thread_id).order_by(ChatMessage.created_at.asc())
            ).scalars().all()

        assert [message.role for message in persisted] == ['user', 'assistant']
        assert persisted[0].content == 'Check wire format compatibility.'
        assert persisted[1].content.startswith('Analyzing\n')
        assert 'Searching\n' in persisted[1].content
        assert 'Reading\n' in persisted[1].content
        assert 'Verifying\n' in persisted[1].content
        assert 'Answering\nI do not have enough evidence' in persisted[1].content
    finally:
        app.dependency_overrides.clear()


def test_patch_thread_updates_title(tmp_path) -> None:
    db_path = tmp_path / 'chat-thread-rename-test.db'
    engine = create_engine(f'sqlite+pysqlite:///{db_path}', future=True)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)

    User.__table__.create(engine)
    ChatThread.__table__.create(engine)
    ChatMessage.__table__.create(engine)

    user_id = uuid.uuid4()
    thread_id = uuid.uuid4()

    with session_factory() as session:
        session.add(User(id=user_id, email='phase3@example.com'))
        session.add(ChatThread(id=thread_id, user_id=user_id, title='New Chat'))
        session.commit()

    def override_get_current_user() -> dict[str, str]:
        return {'id': str(user_id), 'email': 'phase3@example.com'}

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
        response = client.patch(
            f'/chat/threads/{thread_id}',
            json={'title': 'Fiscal 2024 Services Summary'},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['id'] == str(thread_id)
        assert payload['title'] == 'Fiscal 2024 Services Summary'

        with session_factory() as session:
            persisted = session.execute(select(ChatThread).where(ChatThread.id == thread_id)).scalar_one()

        assert persisted.title == 'Fiscal 2024 Services Summary'
    finally:
        app.dependency_overrides.clear()


def test_delete_thread_removes_thread(tmp_path) -> None:
    db_path = tmp_path / 'chat-thread-delete-test.db'
    engine = create_engine(f'sqlite+pysqlite:///{db_path}', future=True)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)

    User.__table__.create(engine)
    ChatThread.__table__.create(engine)
    ChatMessage.__table__.create(engine)

    user_id = uuid.uuid4()
    thread_id = uuid.uuid4()

    with session_factory() as session:
        session.add(User(id=user_id, email='phase3@example.com'))
        session.add(ChatThread(id=thread_id, user_id=user_id, title='Delete me'))
        session.commit()

    def override_get_current_user() -> dict[str, str]:
        return {'id': str(user_id), 'email': 'phase3@example.com'}

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
        response = client.delete(f'/chat/threads/{thread_id}')

        assert response.status_code == 204

        with session_factory() as session:
            persisted = session.execute(select(ChatThread).where(ChatThread.id == thread_id)).scalar_one_or_none()

        assert persisted is None
    finally:
        app.dependency_overrides.clear()


def test_delete_thread_removes_thread_with_citations(tmp_path) -> None:
    db_path = tmp_path / 'chat-thread-delete-with-citations-test.db'
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
    assistant_message_id = uuid.uuid4()
    source_document_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    with session_factory() as session:
        session.add(User(id=user_id, email='phase3@example.com'))
        session.add(SourceDocument(id=source_document_id, company_name='Microsoft', filing_type='10-K', filing_year=2024))
        session.connection().exec_driver_sql(
            """
            INSERT INTO document_chunks (id, source_document_id, content, page_number)
            VALUES (?, ?, ?, ?)
            """,
            (chunk_id.hex, source_document_id.hex, 'Services revenue increased year over year.', 42),
        )
        session.add(ChatThread(id=thread_id, user_id=user_id, title='Delete me with citations'))
        session.add(ChatMessage(id=uuid.uuid4(), thread_id=thread_id, role='user', content='What supports services growth?'))
        session.add(ChatMessage(id=assistant_message_id, thread_id=thread_id, role='assistant', content='Services grew.'))
        session.add(
            MessageCitation(
                message_id=assistant_message_id,
                chunk_id=chunk_id,
                source_document_id=source_document_id,
                quote='Services revenue increased year over year.',
                page_number=42,
            )
        )
        session.commit()

    def override_get_current_user() -> dict[str, str]:
        return {'id': str(user_id), 'email': 'phase3@example.com'}

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
        delete_response = client.delete(f'/chat/threads/{thread_id}')
        assert delete_response.status_code == 204

        list_response = client.get('/chat/threads')
        assert list_response.status_code == 200
        assert all(item['id'] != str(thread_id) for item in list_response.json())

        with session_factory() as session:
            persisted_thread = session.execute(select(ChatThread).where(ChatThread.id == thread_id)).scalar_one_or_none()
            persisted_messages = session.execute(select(ChatMessage).where(ChatMessage.thread_id == thread_id)).scalars().all()
            persisted_citations = session.execute(select(MessageCitation)).scalars().all()

        assert persisted_thread is None
        assert persisted_messages == []
        assert persisted_citations == []
    finally:
        app.dependency_overrides.clear()


def test_create_then_delete_thread_flow(tmp_path) -> None:
    db_path = tmp_path / 'chat-create-then-delete-thread-test.db'
    engine = create_engine(f'sqlite+pysqlite:///{db_path}', future=True)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)

    User.__table__.create(engine)
    ChatThread.__table__.create(engine)
    ChatMessage.__table__.create(engine)

    user_id = uuid.uuid4()
    with session_factory() as session:
        session.add(User(id=user_id, email='phase3@example.com'))
        session.commit()

    def override_get_current_user() -> dict[str, str]:
        return {'id': str(user_id), 'email': 'phase3@example.com'}

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

        create_response = client.post('/chat/threads', json={'title': 'Delete target'})
        assert create_response.status_code == 201
        created_thread_id = create_response.json()['id']

        delete_response = client.delete(f'/chat/threads/{created_thread_id}')
        assert delete_response.status_code == 204

        list_response = client.get('/chat/threads')
        assert list_response.status_code == 200
        assert all(item['id'] != created_thread_id for item in list_response.json())
    finally:
        app.dependency_overrides.clear()


def test_get_thread_messages_includes_citations(tmp_path) -> None:
    db_path = tmp_path / 'chat-message-citations-test.db'
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
    previous_chunk_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    next_chunk_id = uuid.uuid4()
    assistant_message_id = uuid.uuid4()

    with session_factory() as session:
        session.add(User(id=user_id, email='phase3@example.com'))
        session.add(
            SourceDocument(
                id=document_id,
                ticker='MSFT',
                company_name='Microsoft',
                filing_type='10-K',
                filing_year=2024,
                source_url='https://example.com/msft-10k',
            )
        )
        session.connection().exec_driver_sql(
            """
            INSERT INTO document_chunks (id, source_document_id, content, page_number)
            VALUES (?, ?, ?, ?)
            """,
            (previous_chunk_id.hex, document_id.hex, 'Context before: segment demand accelerated in Q3.', 41),
        )
        session.connection().exec_driver_sql(
            """
            INSERT INTO document_chunks (id, source_document_id, content, page_number)
            VALUES (?, ?, ?, ?)
            """,
            (chunk_id.hex, document_id.hex, 'Services revenue increased year over year.', 42),
        )
        session.connection().exec_driver_sql(
            """
            INSERT INTO document_chunks (id, source_document_id, content, page_number)
            VALUES (?, ?, ?, ?)
            """,
            (next_chunk_id.hex, document_id.hex, 'Context after: enterprise customers expanded multi-cloud spend.', 43),
        )
        session.add(ChatThread(id=thread_id, user_id=user_id, title='Phase 7'))
        session.add(ChatMessage(id=uuid.uuid4(), thread_id=thread_id, role='user', content='What supports services growth?'))
        session.add(
            ChatMessage(
                id=assistant_message_id,
                thread_id=thread_id,
                role='assistant',
                content='Microsoft reported services growth.',
            )
        )
        session.add(
            MessageCitation(
                message_id=assistant_message_id,
                chunk_id=chunk_id,
                source_document_id=document_id,
                quote='Services revenue increased year over year.',
                page_number=42,
            )
        )
        session.commit()

    def override_get_current_user() -> dict[str, str]:
        return {'id': str(user_id), 'email': 'phase3@example.com'}

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
        response = client.get(f'/chat/threads/{thread_id}/messages')

        assert response.status_code == 200
        payload = response.json()
        assistant_payload = next(item for item in payload if item['role'] == 'assistant')
        assert len(assistant_payload['citations']) == 1
        citation = assistant_payload['citations'][0]
        assert citation['chunk_id'] == str(chunk_id)
        assert citation['source_document_id'] == str(document_id)
        assert citation['company_name'] == 'Microsoft'
        assert citation['filing_type'] == '10-K'
        assert citation['filing_year'] == 2024
        assert citation['page_number'] == 42
        assert citation['quote'] == 'Services revenue increased year over year.'
        assert citation['excerpt'] == 'Services revenue increased year over year.'
        assert len(citation['neighboring_chunks']) == 2
        assert citation['neighboring_chunks'][0]['relation'] == 'previous'
        assert citation['neighboring_chunks'][0]['page_number'] == 41
        assert citation['neighboring_chunks'][1]['relation'] == 'next'
        assert citation['neighboring_chunks'][1]['page_number'] == 43
    finally:
        app.dependency_overrides.clear()
