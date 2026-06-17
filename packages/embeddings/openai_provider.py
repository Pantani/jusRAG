"""OpenAI-backed embedding provider (implements EmbeddingProvider, §27).

Reads ``OPENAI_API_KEY`` / ``OPENAI_EMBEDDING_MODEL`` from settings. The ``openai``
client is imported lazily inside the constructor so that importing this module
never requires the dependency or a key — unit tests use the fake provider and
must not reach the network (system rules §6, §8).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from packages.config.settings import Settings, get_settings

if TYPE_CHECKING:  # pragma: no cover - typing only
    from openai import OpenAI


class OpenAIEmbeddingProvider:
    """Calls the OpenAI embeddings API. Never exercised in unit tests."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set; cannot use OpenAIEmbeddingProvider. "
                "Configure it in .env or inject the FakeEmbeddingProvider."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise RuntimeError(
                "The 'openai' package is required for OpenAIEmbeddingProvider."
            ) from exc
        self._client: OpenAI = OpenAI(api_key=self._settings.openai_api_key)
        self._model = self._settings.openai_embedding_model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in response.data]

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]
