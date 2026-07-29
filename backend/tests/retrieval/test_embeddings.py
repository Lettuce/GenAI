from __future__ import annotations

import pytest

from app.schemas.config import settings
from app.retrieval.embeddings import embed_query


class _FakeEmbeddingsAPI:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, *, model: str, input: str, dimensions: int) -> object:
        self.calls.append({"model": model, "input": input, "dimensions": dimensions})
        embedding_item = type("EmbeddingItem", (), {"embedding": [0.5, 0.25, -0.25]})
        response_type = type("EmbeddingResponse", (), {"data": [embedding_item]})
        return response_type()


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.embeddings = _FakeEmbeddingsAPI()


def test_embed_query_calls_openai_embeddings_api() -> None:
    client = _FakeOpenAIClient()

    result = embed_query("  cash flow trends ", client)

    assert result == [0.5, 0.25, -0.25]
    assert client.embeddings.calls == [
        {
            "model": settings.embedding_model,
            "input": "cash flow trends",
            "dimensions": settings.embedding_dimensions,
        }
    ]


def test_embed_query_rejects_empty_query() -> None:
    client = _FakeOpenAIClient()

    with pytest.raises(ValueError, match="query must not be empty"):
        embed_query("   ", client)
