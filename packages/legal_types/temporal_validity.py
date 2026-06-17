"""Temporal validity utilities: vigência and versioning of norms (§12.2).

A norm has multiple redações over time. ``version`` is a date-like string
(ISO ``YYYY-MM-DD``, see §9 payload). ``is_current`` flags the redação in force.
These helpers select the correct version for a reference date and detect the
current redação within a set.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date

from packages.legal_types.schemas import LegalChunk


def parse_version_date(version: str) -> date:
    """Parse an ISO ``YYYY-MM-DD`` version string into a ``date``.

    Raises ``ValueError`` on malformed input (no silent fallback, §40).
    """

    return date.fromisoformat(version)


def is_current(chunk: LegalChunk) -> bool:
    """Whether the chunk represents the redação currently in force.

    Reads the ``is_current`` flag from metadata (the §9 payload field);
    absent flag is treated as current (single-version documents).
    """

    flag = chunk.metadata.get("is_current", True)
    return bool(flag)


def current_chunks(chunks: Iterable[LegalChunk]) -> list[LegalChunk]:
    """Filter to chunks whose redação is in force."""

    return [c for c in chunks if is_current(c)]


def select_version_at(
    chunks: Sequence[LegalChunk],
    reference: date,
) -> LegalChunk | None:
    """Return the redação in force at ``reference`` for a set of versions.

    Picks the chunk with the latest ``version`` date not after ``reference``.
    Chunks with unparseable versions are skipped. Returns ``None`` if none
    apply (e.g. the norm did not yet exist at ``reference``).
    """

    best: LegalChunk | None = None
    best_date: date | None = None
    for chunk in chunks:
        try:
            version_date = parse_version_date(chunk.version)
        except ValueError:
            continue
        if version_date > reference:
            continue
        if best_date is None or version_date > best_date:
            best, best_date = chunk, version_date
    return best


def latest_version(chunks: Sequence[LegalChunk]) -> LegalChunk | None:
    """Return the chunk with the most recent parseable ``version`` date."""

    return select_version_at(chunks, date.max)
