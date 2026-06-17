"""Embedding providers behind the ``EmbeddingProvider`` Protocol (§27)."""

from packages.embeddings.base import EmbeddingProvider
from packages.embeddings.fake_provider import FakeEmbeddingProvider

__all__ = ["EmbeddingProvider", "FakeEmbeddingProvider"]
