from __future__ import annotations

import hashlib

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from app.schemas.config import settings


def build_embedding_client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key, max_retries=0)


def build_fallback_embedding(text: str, dimensions: int | None = None) -> list[float]:
    dimension_count = dimensions or settings.embedding_dimensions
    values: list[float] = []
    for index in range(dimension_count):
        digest = hashlib.sha256(f"{text}:{index}".encode("utf-8")).digest()
        values.append(((digest[0] / 255.0) * 2.0) - 1.0)
    return values


def create_embedding(text: str, client: OpenAI) -> list[float]:
    try:
        response = client.embeddings.create(model=settings.embedding_model, input=text)
        return response.data[0].embedding
    except Exception as exc:  # pragma: no cover - exercised via live quota failures
        status_code = getattr(exc, "status_code", None)
        if isinstance(exc, httpx.HTTPStatusError):
            response = exc.response
            status_code = response.status_code if response is not None else None
        if isinstance(exc, APIStatusError) and status_code not in {429, 500, 502, 503, 504}:
            raise
        if isinstance(exc, httpx.HTTPStatusError) and status_code not in {429, 500, 502, 503, 504}:
            raise
        if not isinstance(
            exc,
            (APIConnectionError, APITimeoutError, APIStatusError, RateLimitError, httpx.HTTPStatusError),
        ):
            raise
        return build_fallback_embedding(text, dimensions=settings.embedding_dimensions)


def embed_texts(texts: list[str], client: OpenAI) -> list[list[float]]:
    return [create_embedding(text, client) for text in texts]