"""Application settings loaded from the environment via pydantic-settings.

Secrets and infra coordinates are read from `.env` (see `.env.example`). There are
no silent magic defaults for secrets: a missing required value surfaces as an
explicit validation error at startup.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application configuration.

    Mirrors the keys declared in `.env.example` (§7 of the prompt master).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_env: str = "local"
    app_name: str = "jus-rag-brasil"
    log_level: str = "INFO"

    # Postgres
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str

    # Qdrant
    qdrant_url: str
    qdrant_collection_legal_chunks: str = "legal_chunks"

    # Redis
    redis_url: str

    # OpenAI (key intentionally has no default: must be provided explicitly when used)
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4.1-mini"

    # Provider selection. "fake" enables deterministic offline/demo operation
    # without OPENAI_API_KEY; "openai" (default) preserves production behavior.
    embedding_provider: Literal["openai", "fake", "local"] = "openai"
    llm_provider: Literal["openai", "fake", "ollama"] = "openai"

    # Local providers (Phase 12). Concrete implementations live in
    # packages/embeddings (sentence-transformers) and packages/llm (Ollama HTTP).
    ollama_base_url: str = "http://ollama:11434"
    local_embedding_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    ollama_chat_model: str = "llama3.1:8b"

    # OpenSearch (optional)
    enable_opensearch: bool = False
    opensearch_url: str = "http://opensearch:9200"

    # Run logs
    store_run_logs: bool = True
    anonymize_run_logs: bool = True

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so the `.env` file is parsed once. Validation errors propagate.
    """
    return Settings()  # type: ignore[call-arg]


__all__ = ["Settings", "get_settings"]
