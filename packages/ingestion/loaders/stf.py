"""Local STF case-law loader — placeholder (§12.9).

Structural placeholder for a future phase. STF jurisprudence (súmulas vinculantes,
repercussão geral) is not part of the v0.6 seed; this module exists for symmetry
with :mod:`packages.ingestion.loaders.stj` so consumers can import it without a
conditional. It carries no real logic yet and intentionally has no seed on disk.
"""

from __future__ import annotations

from pathlib import Path

from packages.legal_types.schemas import CaseLawDocument


class StfCaseLawLoader:
    """Placeholder loader for STF case law. Not implemented in v0.6."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> list[CaseLawDocument]:
        raise NotImplementedError(
            "STF case-law ingestion is not implemented yet (planned for a later phase)."
        )
