"""EmbeddingProvider Protocol (§27).

Concrete providers (OpenAI, fake) are swappable behind this interface. Callers
(indexing job, retriever) depend only on this Protocol, never on a concrete
implementation, so unit tests can inject the deterministic fake (system rule §6).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Maps text to dense vectors.

    Implementations must return vectors of a single, fixed dimensionality for a
    given instance. ``embed_query`` and ``embed_texts`` must live in the same
    vector space so cosine similarity is meaningful.
    """

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of documents (used at indexing time)."""
        ...

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query (used at retrieval time)."""
        ...
