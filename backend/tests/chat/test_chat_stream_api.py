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
        assert persisted[1].content.startswith('Stub assistant response:')
    finally:
        app.dependency_overrides.clear()
