"""Derive the vector-DB payload from a LegalChunk (§9).

Centralized so both the Qdrant store and the in-memory test store build the same
payload shape, and so filterable metadata keys stay consistent across stores.
"""

from __future__ import annotations

from typing import Any

from packages.legal_types.schemas import LegalChunk

# Payload keys usable as metadata filters in ``VectorStore.search``.
FILTERABLE_KEYS: tuple[str, ...] = (
    "doc_type",
    "legal_area",
    "source",
    "article",
    "norm_number",
    "norm_year",
    "is_current",
)


def chunk_to_payload(chunk: LegalChunk) -> dict[str, Any]:
    """Project a LegalChunk into the persisted payload (§9)."""

    return {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "doc_type": str(chunk.doc_type),
        "source": str(chunk.source),
        "title": chunk.title,
        "legal_area": str(chunk.legal_area) if chunk.legal_area else None,
        "jurisdiction": chunk.jurisdiction,
        "norm_type": chunk.norm_type,
        "norm_number": chunk.norm_number,
        "norm_year": chunk.norm_year,
        "article": chunk.article,
        "paragraph": chunk.paragraph,
        "inciso": chunk.inciso,
        "alinea": chunk.alinea,
        "text": chunk.text,
        "source_url": chunk.source_url,
        "version": chunk.version,
        "content_hash": chunk.content_hash,
        "is_current": bool(chunk.metadata.get("is_current", True)),
        "metadata": dict(chunk.metadata),
    }


def payload_matches_filters(payload: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    """Return True if the payload satisfies every equality filter."""

    if not filters:
        return True
    for key, expected in filters.items():
        if isinstance(expected, (list, tuple, set)):
            if payload.get(key) not in expected:
                return False
        elif payload.get(key) != expected:
            return False
    return True
