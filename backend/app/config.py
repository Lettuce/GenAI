import os
from pathlib import Path
from typing import Annotated

from pydantic import BeforeValidator, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _split_csv(value: object) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return value
    raise TypeError("allowed_origins must be a comma-separated string or list")


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    database_url: str

    openai_api_key: str
    openai_chat_model: str = "gpt-4o"
    openai_grounding_model: str = "gpt-4o-mini"
    llm_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    retrieval_top_k: int = Field(default=8, ge=1)
    rf_60: int = Field(default=60, ge=1)
    grounding_threshold: float = Field(default=0.75, ge=0.0, le=1.0)

    allowed_origins: Annotated[
        list[str],
        NoDecode,
        BeforeValidator(_split_csv),
    ] = Field(default_factory=list)

    @field_validator("allowed_origins")
    @classmethod
    def validate_allowed_origins(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("ALLOWED_ORIGINS must be set in the environment for this deployment")
        return value

    @property
    def chat_model(self) -> str:
        return self.openai_chat_model

    @property
    def grounding_model(self) -> str:
        return self.openai_grounding_model

    @field_validator("database_url")
    @classmethod
    def reject_transaction_pooler_url(cls, value: str) -> str:
        if ":6543" in value:
            raise ValueError(
                "DATABASE_URL must use the direct or session connection, not the transaction pooler (port 6543)"
            )

        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)

        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)

        return value


settings = Settings()

# OpenAI SDK reads OPENAI_API_KEY from the environment directly.
os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
