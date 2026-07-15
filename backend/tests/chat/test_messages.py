from __future__ import annotations

from app.chat.messages import extract_last_user_text


def test_extract_last_user_text_from_content_field() -> None:
    payload = [
        {"role": "user", "content": "First"},
        {"role": "assistant", "content": "Reply"},
        {"role": "user", "content": "Second"},
    ]

    assert extract_last_user_text(payload) == "Second"


def test_extract_last_user_text_from_ui_parts() -> None:
    payload = [
        {
            "role": "user",
            "parts": [
                {"type": "text", "text": "How did revenue change?"},
            ],
        }
    ]

    assert extract_last_user_text(payload) == "How did revenue change?"
