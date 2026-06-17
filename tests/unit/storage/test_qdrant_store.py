"""QdrantVectorStore: stable point id (idempotency) and lazy import boundary.

The full upsert/search path needs ``qdrant_client`` and a running Qdrant, so it is
not exercised here (system rule §8: no external deps in unit tests). We verify the
deterministic id derivation that guarantees idempotent re-indexing (§28/§40.4).
"""

from __future__ import annotations

from packages.storage.qdrant import _point_id


def test_point_id_is_deterministic() -> None:
    assert _point_id("cdc-8078-1990-art-12") == _point_id("cdc-8078-1990-art-12")


def test_point_id_differs_per_chunk() -> None:
    assert _point_id("cdc-8078-1990-art-12") != _point_id("cdc-8078-1990-art-49")
