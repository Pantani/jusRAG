"""VectorStore Protocol and the search result shape (§28).

The result object carries the chunk payload, a similarity ``score`` and the
``metadata`` block — and nothing framework-specific. This is the boundary the
retriever ranks on; downstream layers (answer, api) consume the retriever's
output, not the raw store result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class VectorSearchResult:
    """A single hit from the vector store (§28, §29).

    ``score`` is the raw vector similarity (cosine, in [-1, 1], typically [0, 1]
    for normalized non-negative embeddings). ``payload`` is the full chunk
    payload as stored; ``metadata`` is the chunk's free-form metadata sub-dict.
    """

    chunk_id: str
    score: float
    text: str
    payload: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class VectorStore(Protocol):
    """Upsert and search dense vectors keyed by stable chunk ids (§28)."""

    def upsert_chunks(self, chunks: list[Any], vectors: list[list[float]]) -> None:
        """Idempotently store chunks with their vectors (id = ``chunk.chunk_id``)."""
        ...

    def search(
        self,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Return the ``top_k`` nearest chunks, optionally filtered by metadata."""
        ...
