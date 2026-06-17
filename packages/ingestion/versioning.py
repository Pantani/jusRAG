"""Content hashing and hash-level idempotency (§8, §40.4).

`content_hash = "sha256:" + sha256(normalized_text)`. The hash uniquely
identifies a chunk's content; re-ingestion is idempotent at the hash level: a
chunk whose hash already exists is neither rewritten nor duplicated. Combined
with `version` (the norm's temporal label), it lets the system tell *content
changed* from *which redaction was in force when*.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator

from packages.ingestion.normalizer import normalize_text
from packages.legal_types.schemas import LegalChunk

HASH_PREFIX = "sha256:"


def content_hash(text: str) -> str:
    """Hash already-normalized text. Returns ``sha256:<hex>``."""

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"{HASH_PREFIX}{digest}"


def hash_for_raw(text: str) -> str:
    """Normalize then hash. Convenience for callers holding raw text."""

    return content_hash(normalize_text(text))


def deduplicate_by_hash(chunks: Iterable[LegalChunk]) -> Iterator[LegalChunk]:
    """Yield chunks dropping any whose ``content_hash`` was already seen.

    Idempotency on re-ingestion: the first occurrence of each hash wins; later
    duplicates are skipped. Order is preserved.
    """

    seen: set[str] = set()
    for chunk in chunks:
        if chunk.content_hash in seen:
            continue
        seen.add(chunk.content_hash)
        yield chunk
