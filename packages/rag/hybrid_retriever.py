"""Hybrid (vector + BM25) retrieval — prepared stub (future phase).

The MVP uses dense vector retrieval only (``LegalRetriever``). Fusing BM25
(OpenSearch) with vector results is a later phase. This stub deliberately
delegates 1:1 to the dense retriever and exposes no fake BM25 signal, so behavior
is honest until the lexical store exists.
"""

from __future__ import annotations

from packages.embeddings.base import EmbeddingProvider
from packages.rag.retriever import LegalRetriever
from packages.rag.types import RetrievalQuery, RetrievedChunk
from packages.storage.base import VectorStore


class HybridRetriever:
    """Phase-3 placeholder: dense-only. Adds BM25 fusion in a later phase."""

    def __init__(self, embeddings: EmbeddingProvider, store: VectorStore) -> None:
        self._dense = LegalRetriever(embeddings, store)

    def retrieve(self, request: RetrievalQuery) -> list[RetrievedChunk]:
        return self._dense.retrieve(request)
