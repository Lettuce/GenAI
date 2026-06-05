import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import CurrentUser, get_access_token, get_current_user
from app.main import app
from app.schemas.chat import ThreadResponse

TEST_USER = CurrentUser(id=uuid.uuid4(), email="analyst@example.com")
OTHER_USER = CurrentUser(id=uuid.uuid4(), email="other@example.com")
THREAD_ID = uuid.uuid4()
NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    app.dependency_overrides[get_access_token] = lambda: "test-token"
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_get_threads_returns_thread_list(client: TestClient) -> None:
    thread = ThreadResponse(id=THREAD_ID, title="Test", created_at=NOW, updated_at=NOW)

    with (
        patch("app.api.chat.ensure_user", AsyncMock()),
        patch("app.api.chat.create_user_client", AsyncMock(return_value=MagicMock())),
        patch("app.api.chat.list_threads", AsyncMock(return_value=[thread])),
    ):
        response = client.get("/chat/threads", headers={"Authorization": "Bearer test"})

    assert response.status_code == 200
    body = response.json()
    assert body["threads"][0]["id"] == str(THREAD_ID)
    assert body["threads"][0]["createdAt"] == NOW.isoformat().replace("+00:00", "Z")


def test_post_thread_creates_thread(client: TestClient) -> None:
    thread = ThreadResponse(id=THREAD_ID, title="New chat", created_at=NOW, updated_at=NOW)

    with (
        patch("app.api.chat.ensure_user", AsyncMock()),
        patch("app.api.chat.create_user_client", AsyncMock(return_value=MagicMock())),
        patch("app.api.chat.create_thread", AsyncMock(return_value=thread)),
    ):
        response = client.post(
            "/chat/threads",
            headers={"Authorization": "Bearer test"},
            json={"title": "New chat"},
        )

    assert response.status_code == 200
    assert response.json()["id"] == str(THREAD_ID)


def test_get_messages_returns_403_for_foreign_thread(client: TestClient) -> None:
    from fastapi import HTTPException

    with patch(
        "app.api.chat.require_thread_access",
        AsyncMock(
            side_effect=HTTPException(status_code=403, detail="Forbidden"),
        ),
    ):
        response = client.get(
            f"/chat/threads/{THREAD_ID}/messages",
            headers={"Authorization": "Bearer test"},
        )

    assert response.status_code == 403


def test_post_stream_returns_event_stream(client: TestClient) -> None:
    from app.database.chats import ThreadRow

    thread = ThreadRow(id=THREAD_ID, user_id=TEST_USER.id, title="New chat")

    async def fake_stream(**kwargs):
        yield 'data: {"type":"text-start","id":"msg-1"}\n\n'
        yield 'data: {"type":"text-end","id":"msg-1"}\n\n'

    with (
        patch("app.api.chat.ensure_user", AsyncMock()),
        patch("app.api.chat.require_thread_access", AsyncMock(return_value=thread)),
        patch("app.api.chat.create_user_client", AsyncMock(return_value=MagicMock())),
        patch("app.api.chat.stream_stub_and_persist", fake_stream),
    ):
        response = client.post(
            "/chat/stream",
            headers={"Authorization": "Bearer test"},
            json={
                "threadId": str(THREAD_ID),
                "messages": [
                    {
                        "role": "user",
                        "parts": [{"type": "text", "text": "Hello"}],
                    }
                ],
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "text-start" in response.text
