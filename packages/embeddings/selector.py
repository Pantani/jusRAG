"""Config-driven selection of the embedding provider (§EMBEDDING_PROVIDER).

Single source of truth shared by the API DI (``apps/api/dependencies.py``) and the
indexing job (``apps/worker/jobs/index_cdc.py``) so the chosen provider and the
Qdrant collection vector size never drift apart.

- ``fake``  -> ``FakeEmbeddingProvider`` (deterministic, no network, no key).
- ``openai`` -> ``OpenAIEmbeddingProvider`` (raises explicitly without a key; no
  silent fallback, per system rules §2/§6).

The vector size of the ``legal_chunks`` collection MUST match the selected
provider: 1536 for OpenAI's ``text-embedding-3-small``, and the fake provider's
``dim`` (256) otherwise. Switching providers on an existing collection requires
recreating it.
"""

from __future__ import annotations

from packages.config.settings import Settings, get_settings
from packages.embeddings.base import EmbeddingProvider
from packages.embeddings.fake_provider import FakeEmbeddingProvider
from packages.embeddings.openai_provider import OpenAIEmbeddingProvider

# OpenAI text-embedding-3-small dimensionality (real provider).
OPENAI_EMBEDDING_DIM = 1536


def make_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Return the embedding provider selected by ``settings.embedding_provider``."""

    settings = settings or get_settings()
    if settings.embedding_provider == "fake":
        return FakeEmbeddingProvider()
    return OpenAIEmbeddingProvider(settings)


def embedding_vector_size(settings: Settings | None = None) -> int:
    """Vector size of the collection for the selected provider."""

    settings = settings or get_settings()
    if settings.embedding_provider == "fake":
        return FakeEmbeddingProvider().dim
    return OPENAI_EMBEDDING_DIM


__all__ = [
    "OPENAI_EMBEDDING_DIM",
    "embedding_vector_size",
    "make_embedding_provider",
]
