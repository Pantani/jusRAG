"""content_hash format/stability and hash-level dedup."""

from __future__ import annotations

from datetime import UTC, datetime

from packages.ingestion.versioning import (
    HASH_PREFIX,
    content_hash,
    deduplicate_by_hash,
    hash_for_raw,
)
from packages.legal_types.enums import DocType, Source
from packages.legal_types.schemas import LegalChunk


def _chunk(chunk_id: str, hash_: str) -> LegalChunk:
    return LegalChunk(
        chunk_id=chunk_id,
        document_id="cdc-8078-1990",
        doc_type=DocType.STATUTE,
        source=Source.PLANALTO,
        title="CDC",
        text="x",
        version="2026-06-16",
        content_hash=hash_,
        created_at=datetime(2026, 6, 16, tzinfo=UTC),
    )


def test_hash_format_and_determinism() -> None:
    h = content_hash("texto normalizado")
    assert h.startswith(HASH_PREFIX)
    assert len(h) == len(HASH_PREFIX) + 64
    assert h == content_hash("texto normalizado")


def test_hash_for_raw_normalizes_before_hashing() -> None:
    assert hash_for_raw("a   b\r\n") == hash_for_raw("a b")


def test_deduplicate_keeps_first_drops_repeat_hash() -> None:
    a = _chunk("art-1", "sha256:aa")
    b = _chunk("art-2", "sha256:bb")
    a_dup = _chunk("art-1-again", "sha256:aa")
    out = list(deduplicate_by_hash([a, b, a_dup]))
    assert [c.chunk_id for c in out] == ["art-1", "art-2"]
