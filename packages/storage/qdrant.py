"""Qdrant-backed VectorStore (implements §28).

Idempotent: point id is derived from the stable ``chunk_id`` so re-indexing
overwrites instead of duplicating. ``qdrant_client`` is imported lazily so this
module imports without the dependency and unit tests never touch it (they use the
in-memory store). This class knows nothing about FastAPI or the LLM.
"""

from __future__ import annotations

import uuid
from typing import Any

from packages.legal_types.schemas import LegalChunk
from packages.storage.base import VectorSearchResult
from packages.storage.payload import chunk_to_payload

# Deterministic namespace so chunk_id -> point uuid is stable across runs.
_POINT_NAMESPACE = uuid.UUID("6f9a1c2e-0000-4000-8000-000000000001")


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(_POINT_NAMESPACE, chunk_id))


class QdrantVectorStore:
    """Vector store over a single Qdrant collection (default ``legal_chunks``)."""

    def __init__(
        self,
        *,
        url: str,
        collection: str = "legal_chunks",
        vector_size: int,
        client: Any | None = None,
    ) -> None:
        self._collection = collection
        self._vector_size = vector_size
        if client is not None:
            self._client = client
        else:  # pragma: no cover - requires a running Qdrant
            from qdrant_client import QdrantClient

            self._client = QdrantClient(url=url)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        from qdrant_client import models

        if self._client.collection_exists(self._collection):
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=models.VectorParams(
                size=self._vector_size, distance=models.Distance.COSINE
            ),
        )

    def upsert_chunks(self, chunks: list[LegalChunk], vectors: list[list[float]]) -> None:
        from qdrant_client import models

        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors length mismatch")
        points = [
            models.PointStruct(
                id=_point_id(chunk.chunk_id),
                vector=vector,
                payload=chunk_to_payload(chunk),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        if points:
            self._client.upsert(collection_name=self._collection, points=points)

    def _build_filter(self, filters: dict[str, Any] | None) -> Any:
        from qdrant_client import models

        if not filters:
            return None
        conditions: list[models.Condition] = [
            models.FieldCondition(key=key, match=models.MatchValue(value=value))
            for key, value in filters.items()
        ]
        return models.Filter(must=conditions)

    def search(
        self,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        hits = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            limit=top_k,
            query_filter=self._build_filter(filters),
            with_payload=True,
        ).points
        results: list[VectorSearchResult] = []
        for hit in hits:
            payload: dict[str, Any] = hit.payload or {}
            results.append(
                VectorSearchResult(
                    chunk_id=payload.get("chunk_id", str(hit.id)),
                    score=float(hit.score),
                    text=payload.get("text", ""),
                    payload=payload,
                    metadata=dict(payload.get("metadata", {})),
                )
            )
        return results
