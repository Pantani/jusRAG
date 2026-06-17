"""Cross-encoder reranker — prepared stub (future phase).

No real reranking in Phase 3. ``rerank`` is an identity pass-through that
preserves the legal ranker's order; it does not fabricate scores. A real
cross-encoder (behind a Protocol) replaces this in a later phase.
"""

from __future__ import annotations

from packages.rag.types import RetrievedChunk


class NoOpReranker:
    """Identity reranker: returns the input order unchanged (top_k truncation)."""

    def rerank(
        self, query: str, chunks: list[RetrievedChunk], top_k: int | None = None
    ) -> list[RetrievedChunk]:
        return chunks if top_k is None else chunks[:top_k]
