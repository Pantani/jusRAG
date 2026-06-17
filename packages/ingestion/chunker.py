"""Structural chunker for legislation (§12.3, §18).

Chunking is **by normative structure**, not by token window. The primary unit
is the *article* — the verifiable citation unit. Each article becomes one
`LegalChunk` carrying full legal metadata + a stable `chunk_id` + `content_hash`,
so it is citable in isolation.

Markdown contract (produced by the seed / loaders):
- Each article starts with a heading ``## Art. <N>`` (e.g. ``## Art. 6º``,
  ``## Art. 12``). Everything until the next article heading is that article's
  body, including its ``§`` paragraphs, ``I/II`` incisos and ``a)/b)`` alíneas.
- Text before the first article heading (preamble) is ignored for chunking.

The article number is normalized for the id (``6º`` -> ``6``) while the rendered
form is kept in `article` for display. Internal structure is preserved inside
`text`; the structural fields (paragraph/inciso/alinea) stay ``None`` at the
article granularity but remain available for finer chunking later.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import UTC, date, datetime

from packages.ingestion.loaders.base import RawDocument
from packages.ingestion.normalizer import normalize_text
from packages.ingestion.versioning import content_hash
from packages.legal_types.citations import build_chunk_id
from packages.legal_types.enums import DocType
from packages.legal_types.schemas import CaseLawDocument, LegalChunk

# Matches an article heading line: "## Art. 6º", "## Art. 12", "## Art. 14-A".
_ARTICLE_HEADING_RE = re.compile(
    r"^\s{0,3}#{1,6}\s*Art\.?\s*(?P<num>\d+(?:-[A-Z])?)\s*(?P<ord>[ºo°]?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Ordinal articles (1-9) render as "6º"; from 10 on, "12".
_ORDINAL_LIMIT = 10


def _render_article(num: str) -> str:
    """Render the display form of an article number ("6" -> "6º", "12" -> "12")."""

    base = num.split("-")[0]
    if base.isdigit() and int(base) < _ORDINAL_LIMIT:
        return f"{num}º"
    return num


def _id_article(num: str) -> str:
    """Id-safe article token (lowercase, no ordinal mark): "6º" -> "6"."""

    return num.lower()


def iter_article_sections(body: str) -> Iterator[tuple[str, str]]:
    """Yield ``(article_num, section_text)`` for each article in ``body``.

    ``section_text`` is the heading line plus the article body up to the next
    article heading. Preamble before the first heading is skipped.
    """

    matches = list(_ARTICLE_HEADING_RE.finditer(body))
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        section = body[match.start() : end]
        yield match.group("num"), section


def chunk_document(
    raw: RawDocument,
    *,
    document_id: str | None = None,
    created_at: datetime | None = None,
) -> list[LegalChunk]:
    """Parse ``raw`` into one `LegalChunk` per article.

    Deterministic: ids derive from the structural address and the hash from the
    normalized text, so re-running yields identical chunks (idempotency §40.4).
    ``created_at`` defaults to "now"; pass a fixed value for byte-stable output.
    """

    short_name = raw.short_name or raw.title
    doc_id = document_id or build_chunk_id(
        short_name=short_name,
        norm_number=raw.norm_number,
        norm_year=raw.norm_year,
    )
    ts = created_at or datetime.now(UTC)

    chunks: list[LegalChunk] = []
    for num, section in iter_article_sections(raw.text):
        normalized = normalize_text(section)
        chunk_id = build_chunk_id(
            short_name=short_name,
            norm_number=raw.norm_number,
            norm_year=raw.norm_year,
            article=_id_article(num),
        )
        chunks.append(
            LegalChunk(
                chunk_id=chunk_id,
                document_id=doc_id,
                doc_type=DocType.STATUTE,
                source=raw.source,
                title=raw.title,
                legal_area=raw.legal_area,
                jurisdiction=raw.jurisdiction,
                norm_type=raw.norm_type,
                norm_number=raw.norm_number,
                norm_year=raw.norm_year,
                article=_render_article(num),
                paragraph=None,
                inciso=None,
                alinea=None,
                text=normalized,
                source_url=raw.source_url,
                version=raw.version,
                content_hash=content_hash(normalized),
                created_at=ts,
                metadata={"is_current": True},
            )
        )
    return chunks


def _date_iso(value: date | None) -> str | None:
    """Serialize an optional date to ISO for payload metadata (§9)."""

    return value.isoformat() if value is not None else None


def chunk_case_law(
    doc: CaseLawDocument,
    *,
    created_at: datetime | None = None,
) -> LegalChunk | None:
    """Turn a `CaseLawDocument` ementa into a single citable `LegalChunk`.

    The ementa (súmula enunciado / acórdão summary) is the citation unit for
    jurisprudence — one chunk per document, mirroring "one article per chunk"
    for statutes. ``doc_type`` is ``case_law``; the §9 case-law payload fields
    (court, case_number, precedent_type, is_binding, judgment/publication dates,
    source_url, content_hash) ride in ``metadata`` so they reach the vector-DB
    payload without changing the `LegalChunk` schema. Returns ``None`` when the
    document has no ementa (jurisprudence without source is not emitted, §22).
    """

    ementa = (doc.ementa or "").strip()
    if not ementa:
        return None
    ts = created_at or datetime.now(UTC)
    normalized = normalize_text(ementa)
    return LegalChunk(
        chunk_id=doc.document_id,
        document_id=doc.document_id,
        doc_type=DocType.CASE_LAW,
        source=doc.source,
        title=f"{doc.court} {doc.case_number}".strip() if doc.case_number else doc.court,
        legal_area=doc.legal_area,
        jurisdiction=None,
        norm_type=None,
        norm_number=None,
        norm_year=None,
        article=None,
        paragraph=None,
        inciso=None,
        alinea=None,
        text=normalized,
        source_url=doc.source_url,
        version=_date_iso(doc.judgment_date) or "",
        content_hash=content_hash(normalized),
        created_at=ts,
        metadata={
            "is_current": True,
            "court": doc.court,
            "case_number": doc.case_number,
            "rapporteur": doc.rapporteur,
            "panel": doc.panel,
            "precedent_type": str(doc.precedent_type) if doc.precedent_type else None,
            "is_binding": doc.is_binding,
            "judgment_date": _date_iso(doc.judgment_date),
            "publication_date": _date_iso(doc.publication_date),
        },
    )


def chunk_case_law_documents(
    docs: list[CaseLawDocument],
    *,
    created_at: datetime | None = None,
) -> list[LegalChunk]:
    """Chunk a list of case-law documents, dropping those without an ementa."""

    chunks = (chunk_case_law(doc, created_at=created_at) for doc in docs)
    return [chunk for chunk in chunks if chunk is not None]
