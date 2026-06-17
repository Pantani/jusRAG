"""Config-driven selection of the embedding provider (§EMBEDDING_PROVIDER).

Single source of truth shared by the API DI (``apps/api/dependencies.py``) and the
indexing job (``apps/worker/jobs/index_cdc.py``) so the chosen provider and the
Qdrant collection vector size never drift apart.

- ``fake``  -> ``FakeEmbeddingProvider`` (deterministic, no network, no key).
- ``openai`` -> ``OpenAIEmbeddingProvider`` (raises explicitly without a key; no
  silent fallback, per system rules §2/§6).
- ``local`` -> ``LocalEmbeddingProvider`` (sentence-transformers; raises if the
  optional ``[local]`` extra is not installed — no silent fallback).

The vector size of the ``legal_chunks`` collection MUST match the selected
provider: 1536 for OpenAI's ``text-embedding-3-small``, and the fake provider's
``dim`` (256) otherwise. Switching providers on an existing collection requires
recreating it.
"""

from __future__ import annotations

from packages.config.settings import Settings, get_settings
from packages.embeddings.base import EmbeddingProvider
from packages.embeddings.fake_provider import FakeEmbeddingProvider
from packages.embeddings.local_provider import LocalEmbeddingProvider
from packages.embeddings.openai_provider import OpenAIEmbeddingProvider

# OpenAI text-embedding-3-small dimensionality (real provider).
OPENAI_EMBEDDING_DIM = 1536

# paraphrase-multilingual-mpnet-base-v2 dimensionality (default local model).
LOCAL_EMBEDDING_DIM = 768


def make_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Return the embedding provider selected by ``settings.embedding_provider``."""

    settings = settings or get_settings()
    provider = str(settings.embedding_provider)
    if provider == "fake":
        return FakeEmbeddingProvider()
    if provider == "local":
        return LocalEmbeddingProvider(model_name=settings.local_embedding_model)
    if provider == "openai":
        return OpenAIEmbeddingProvider(settings)
    raise RuntimeError(f"Unknown embedding_provider: {provider!r}")


def embedding_vector_size(settings: Settings | None = None) -> int:
    """Vector size of the collection for the selected provider."""

    settings = settings or get_settings()
    provider = str(settings.embedding_provider)
    if provider == "fake":
        return FakeEmbeddingProvider().dim
    if provider == "local":
        return LOCAL_EMBEDDING_DIM
    if provider == "openai":
        return OPENAI_EMBEDDING_DIM
    raise RuntimeError(f"Unknown embedding_provider: {provider!r}")


__all__ = [
    "LOCAL_EMBEDDING_DIM",
    "OPENAI_EMBEDDING_DIM",
    "embedding_vector_size",
    "make_embedding_provider",
]
