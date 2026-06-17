"""Repositories over the storage layer.

Thin orchestration over an ``EmbeddingProvider`` + ``VectorStore``: embed chunks
then upsert them. Keeps the indexing job free of provider/store wiring details
and stays agnostic to the concrete implementations (Protocols only, §6/§28).
"""

from __future__ import annotations

from packages.embeddings.base import EmbeddingProvider
from packages.legal_types.schemas import LegalChunk
from packages.storage.base import VectorStore


class ChunkRepository:
    """Indexes ``LegalChunk``s into a vector store via an embedding provider."""

    def __init__(self, embeddings: EmbeddingProvider, store: VectorStore) -> None:
        self._embeddings = embeddings
        self._store = store

    def index_chunks(self, chunks: list[LegalChunk]) -> int:
        """Embed and upsert chunks (idempotent at the store level). Returns count."""

        if not chunks:
            return 0
        vectors = self._embeddings.embed_texts([c.text for c in chunks])
        self._store.upsert_chunks(chunks, vectors)
        return len(chunks)
