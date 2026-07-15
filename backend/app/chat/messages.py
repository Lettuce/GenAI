from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def _coerce_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type in {"text", "input_text"} and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif item_type == "text" and isinstance(item.get("value"), str):
                parts.append(item["value"])
        return "\n".join(part for part in parts if part)

    return ""


def _coerce_text_parts(parts: Any) -> str:
    if not isinstance(parts, list):
        return ""

    text_parts: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text" and isinstance(part.get("text"), str):
            text_parts.append(part["text"])

    return "\n".join(part for part in text_parts if part)


def extract_last_user_text(messages: Iterable[dict[str, Any]]) -> str:
    last_user_message = ""
    for message in messages:
        if message.get("role") != "user":
            continue
        content = _coerce_text_content(message.get("content"))
        if not content.strip():
            content = _coerce_text_parts(message.get("parts"))
        if content.strip():
            last_user_message = content.strip()

    return last_user_message
