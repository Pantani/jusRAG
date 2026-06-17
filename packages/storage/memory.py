"""In-memory VectorStore for unit/integration tests and offline demos.

Ranks by cosine similarity. No network, no external service. Mirrors the
``VectorStore`` Protocol (§28) and the Qdrant payload shape so tests exercise the
same contract the real store honors.
"""

from __future__ import annotations

import math
from typing import Any

from packages.legal_types.schemas import LegalChunk
from packages.storage.base import VectorSearchResult
from packages.storage.payload import chunk_to_payload, payload_matches_filters


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("vector dimensionality mismatch")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class InMemoryVectorStore:
    """Dict-backed vector store keyed by stable ``chunk_id`` (idempotent upsert)."""

    def __init__(self) -> None:
        self._payloads: dict[str, dict[str, Any]] = {}
        self._vectors: dict[str, list[float]] = {}

    def upsert_chunks(self, chunks: list[LegalChunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors length mismatch")
        for chunk, vector in zip(chunks, vectors, strict=True):
            self._payloads[chunk.chunk_id] = chunk_to_payload(chunk)
            self._vectors[chunk.chunk_id] = list(vector)

    def __len__(self) -> int:
        return len(self._payloads)

    def search(
        self,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        scored: list[VectorSearchResult] = []
        for chunk_id, payload in self._payloads.items():
            if not payload_matches_filters(payload, filters):
                continue
            score = _cosine(query_vector, self._vectors[chunk_id])
            scored.append(
                VectorSearchResult(
                    chunk_id=chunk_id,
                    score=score,
                    text=payload["text"],
                    payload=payload,
                    metadata=dict(payload.get("metadata", {})),
                )
            )
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]
