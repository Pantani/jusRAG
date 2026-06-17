"""Loader interface and the raw-document carrier (§5, §12.3).

A loader's single job is to fetch bytes/text from a source and expose them as a
`RawDocument` together with provenance. Parsing/structuring is the chunker's job,
not the loader's. Loaders never embed or persist anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from packages.legal_types.enums import LegalArea, Source


@dataclass(frozen=True, slots=True)
class RawDocument:
    """Raw text plus the provenance needed to build citable chunks.

    `text` is the unparsed document body (markdown for the MVP seed). The
    structural address (article/paragraph/inciso/alinea) is derived later by the
    chunker; here we only carry document-level metadata.
    """

    text: str
    title: str
    source: Source
    source_url: str | None
    version: str
    norm_type: str | None = None
    norm_number: str | None = None
    norm_year: str | None = None
    short_name: str | None = None
    legal_area: LegalArea | None = None
    jurisdiction: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class DocumentLoader(Protocol):
    """Fetches a raw document from some source.

    Implementations: `LocalMarkdownLoader` (MVP). Official sources
    (planalto/lexml/stj/stf) plug in here without changing consumers.
    """

    def load(self) -> RawDocument: ...
