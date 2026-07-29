from __future__ import annotations

from openai import OpenAI

from app.schemas.config import settings


def build_embedding_client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key, max_retries=0)


def embed_query(query: str, client: OpenAI) -> list[float]:
    trimmed_query = query.strip()
    if not trimmed_query:
        raise ValueError("query must not be empty")

    response = client.embeddings.create(
        model=settings.embedding_model,
        input=trimmed_query,
        dimensions=settings.embedding_dimensions,
    )
    return response.data[0].embedding
