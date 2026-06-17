"""Local markdown loader for the CDC seed (§12.3, §18).

Reads a markdown file whose head carries a small key/value provenance block
(``key: value`` lines inside an HTML comment), then exposes the body as a
`RawDocument`. No network — the file is on disk (regra §40.8).

Provenance block example (top of the file)::

    <!--
    short_name: cdc
    title: Código de Defesa do Consumidor
    source: planalto
    source_url: https://www.planalto.gov.br/ccivil_03/leis/l8078.htm
    norm_type: lei
    norm_number: 8078
    norm_year: 1990
    version: 2026-06-16
    legal_area: consumer
    jurisdiction: federal
    -->
"""

from __future__ import annotations

import re
from pathlib import Path

from packages.ingestion.loaders.base import DocumentLoader, RawDocument
from packages.legal_types.enums import LegalArea, Source

_BLOCK_RE = re.compile(r"<!--(?P<block>.*?)-->", re.DOTALL)
_KV_RE = re.compile(r"^\s*(?P<key>[a-z_]+)\s*:\s*(?P<value>.+?)\s*$")

_REQUIRED_KEYS = ("short_name", "title", "source", "version")


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Split the leading provenance comment from the markdown body.

    Returns ``(metadata, body)``. Raises ``ValueError`` if the block is missing
    or a required key is absent — no silent defaults for provenance (§40.4).
    """

    match = _BLOCK_RE.match(text.lstrip("﻿").lstrip())
    if match is None:
        raise ValueError("missing provenance comment block at top of markdown")
    meta: dict[str, str] = {}
    for line in match.group("block").splitlines():
        kv = _KV_RE.match(line)
        if kv:
            meta[kv.group("key")] = kv.group("value")
    missing = [k for k in _REQUIRED_KEYS if k not in meta]
    if missing:
        raise ValueError(f"missing required provenance keys: {missing}")
    body = text[match.end() :]
    return meta, body


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


class LocalMarkdownLoader(DocumentLoader):
    """Loads a single structured markdown legal document from disk."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> RawDocument:
        if not self._path.is_file():
            raise FileNotFoundError(f"seed file not found: {self._path}")
        text = self._path.read_text(encoding="utf-8")
        meta, body = parse_front_matter(text)
        return RawDocument(
            text=body,
            title=meta["title"],
            source=_coerce_source(meta["source"]),
            source_url=meta.get("source_url"),
            version=meta["version"],
            norm_type=meta.get("norm_type"),
            norm_number=meta.get("norm_number"),
            norm_year=meta.get("norm_year"),
            short_name=meta["short_name"],
            legal_area=_coerce_area(meta.get("legal_area")),
            jurisdiction=meta.get("jurisdiction"),
            metadata={},
        )
