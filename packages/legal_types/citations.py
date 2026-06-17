"""Citation utilities: stable chunk ids and LegalCitation construction (§12.2).

The chunk id is the canonical, stable address of a piece of legislation, e.g.
``cdc-8078-1990-art-12`` or ``cdc-8078-1990-art-6-par-1-inc-i``. It must be
deterministic so re-ingestion is idempotent.
"""

from __future__ import annotations

import re

from packages.legal_types.enums import SupportLevel
from packages.legal_types.schemas import (
    CaseLawDocument,
    LegalChunk,
    LegalCitation,
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Lowercase, collapse non-alphanumerics to single dashes, trim dashes."""

    return _SLUG_RE.sub("-", value.strip().lower()).strip("-")


def build_chunk_id(
    *,
    short_name: str,
    norm_number: str | None,
    norm_year: str | None,
    article: str | None = None,
    paragraph: str | None = None,
    inciso: str | None = None,
    alinea: str | None = None,
) -> str:
    """Build a stable chunk id from a norm's structural address.

    Example: ``build_chunk_id(short_name="cdc", norm_number="8078",
    norm_year="1990", article="12")`` -> ``cdc-8078-1990-art-12``.
    """

    parts: list[str] = [slugify(short_name)]
    for value in (norm_number, norm_year):
        if value:
            parts.append(slugify(value))
    for label, value in (
        ("art", article),
        ("par", paragraph),
        ("inc", inciso),
        ("ali", alinea),
    ):
        if value:
            parts.append(f"{label}-{slugify(value)}")
    return "-".join(parts)


def citation_from_chunk(
    chunk: LegalChunk,
    *,
    support_level: SupportLevel = SupportLevel.DIRECT,
    citation_id: str | None = None,
) -> LegalCitation:
    """Construct a LegalCitation from a statute chunk."""

    return LegalCitation(
        citation_id=citation_id or chunk.chunk_id,
        source=chunk.source,
        doc_type=chunk.doc_type,
        title=chunk.title,
        source_url=chunk.source_url,
        article=chunk.article,
        support_level=support_level,
        chunk_id=chunk.chunk_id,
    )


def citation_from_case_law(
    doc: CaseLawDocument,
    *,
    support_level: SupportLevel = SupportLevel.SUPPORTING,
    title: str | None = None,
    chunk_id: str | None = None,
) -> LegalCitation:
    """Construct a LegalCitation from a case-law document."""

    return LegalCitation(
        citation_id=doc.document_id,
        source=doc.source,
        doc_type=doc.doc_type,
        title=title or (doc.case_number or doc.court),
        source_url=doc.source_url,
        case_number=doc.case_number,
        court=doc.court,
        judgment_date=doc.judgment_date,
        publication_date=doc.publication_date,
        support_level=support_level,
        chunk_id=chunk_id,
    )


def format_citation(citation: LegalCitation) -> str:
    """Human-readable, stable rendering for display in answers."""

    if citation.case_number:
        head = f"{citation.court or ''} {citation.case_number}".strip()
    else:
        head = citation.title
    if citation.article:
        head = f"{head}, art. {citation.article}"
    return head
