"""Local STJ case-law loader (§12.9, §22).

Reads a small JSONL seed of public STJ *súmulas* (consumer law) and produces
normalized `CaseLawDocument`s. The seed carries only public, short, non-sigiloso
enunciados — no PII, no sealed-case numbers (regra §40). No network: the file is
on disk; downloading the literal súmula text happens only when authoring the seed.

Seed line shape (one JSON object per line)::

    {
      "summary_number": "297",
      "court": "STJ",
      "source": "stj",
      "precedent_type": "summary",
      "is_binding": false,
      "legal_area": "consumer",
      "judgment_date": "2004-05-12",
      "publication_date": "2004-09-09",
      "ementa": "O Código de Defesa do Consumidor é aplicável às instituições financeiras.",
      "source_url": "https://www.stj.jus.br/..."
    }

The ``ementa`` (the súmula enunciado) is normalized before hashing so the
``content_hash`` and ``document_id`` are stable across runs (idempotency §40.4).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

from packages.ingestion.normalizer import normalize_text
from packages.ingestion.versioning import content_hash
from packages.legal_types.citations import slugify
from packages.legal_types.enums import DocType, LegalArea, PrecedentType, Source
from packages.legal_types.schemas import CaseLawDocument

_REQUIRED_KEYS = ("summary_number", "court", "source", "ementa")


def _parse_date(value: str | None) -> date | None:
    """Parse an ISO date, or ``None``. Raises on malformed input (no fallback)."""

    if value is None:
        return None
    return date.fromisoformat(value)


def _coerce_source(value: str) -> Source:
    try:
        return Source(value)
    except ValueError:
        return Source.UNKNOWN


def _coerce_area(value: str | None) -> LegalArea | None:
    if value is None:
        return None
    try:
        return LegalArea(value)
    except ValueError:
        return LegalArea.UNKNOWN


def _coerce_precedent(value: str | None) -> PrecedentType | None:
    if value is None:
        return None
    try:
        return PrecedentType(value)
    except ValueError:
        return PrecedentType.UNKNOWN


def _build_document(entry: dict[str, object]) -> CaseLawDocument:
    """Map one seed entry to a normalized `CaseLawDocument`."""

    missing = [k for k in _REQUIRED_KEYS if k not in entry]
    if missing:
        raise ValueError(f"missing required case-law keys: {missing}")

    court = str(entry["court"])
    summary_number = str(entry["summary_number"])
    case_number = f"Súmula {summary_number}"
    document_id = slugify(f"{court}-sumula-{summary_number}")
    ementa = normalize_text(str(entry["ementa"]))

    return CaseLawDocument(
        document_id=document_id,
        doc_type=DocType.CASE_LAW,
        source=_coerce_source(str(entry["source"])),
        court=court,
        case_number=case_number,
        rapporteur=entry.get("rapporteur"),  # type: ignore[arg-type]
        panel=entry.get("panel"),  # type: ignore[arg-type]
        judgment_date=_parse_date(entry.get("judgment_date")),  # type: ignore[arg-type]
        publication_date=_parse_date(entry.get("publication_date")),  # type: ignore[arg-type]
        legal_area=_coerce_area(entry.get("legal_area")),  # type: ignore[arg-type]
        precedent_type=_coerce_precedent(entry.get("precedent_type")),  # type: ignore[arg-type]
        is_binding=bool(entry.get("is_binding", False)),
        ementa=ementa,
        full_text=ementa,
        source_url=entry.get("source_url"),  # type: ignore[arg-type]
        content_hash=content_hash(ementa),
        metadata={"summary_number": summary_number},
    )


class StjCaseLawLoader:
    """Loads STJ case-law (súmulas) seed from a local JSONL file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> list[CaseLawDocument]:
        if not self._path.is_file():
            raise FileNotFoundError(f"case-law seed file not found: {self._path}")
        return list(self._iter_documents())

    def _iter_documents(self) -> Iterator[CaseLawDocument]:
        text = self._path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            yield _build_document(json.loads(stripped))
