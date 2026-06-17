"""Shared domain schemas for jus-rag-brasil (§8).

These are the single source of truth consumed by ingestion, storage, retrieval,
answer and agentic modules. Field sets are the exact minima of §8 — do not
reduce them. Validation lives in the models, not in the callers.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from packages.legal_types.enums import (
    DocType,
    LegalArea,
    PrecedentType,
    Source,
    SupportLevel,
)


class SourceMetadata(BaseModel):
    """Provenance block persisted for every document/chunk (§18, system rule §40.4).

    Carries the audit trail required for idempotent, hash-level re-ingestion.
    """

    source: Source
    source_url: str | None = None
    version: str
    content_hash: str = Field(..., description="e.g. 'sha256:<hex>'")
    ingested_at: datetime
    is_current: bool = True


class LegalDocument(BaseModel):
    """A whole legislative document (§8)."""

    document_id: str
    doc_type: DocType
    source: Source
    title: str
    legal_area: LegalArea | None = None
    country: str = "BR"
    jurisdiction: str | None = None
    norm_type: str | None = None
    norm_number: str | None = None
    norm_year: str | None = None
    version: str
    source_url: str | None = None
    content_hash: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class LegalChunk(BaseModel):
    """A retrievable slice of a legislative document (§8).

    Carries the parent document fields plus the structural address
    (article/paragraph/inciso/alinea) and the chunk text.
    """

    chunk_id: str
    document_id: str
    doc_type: DocType
    source: Source
    title: str
    legal_area: LegalArea | None = None
    country: str = "BR"
    jurisdiction: str | None = None
    norm_type: str | None = None
    norm_number: str | None = None
    norm_year: str | None = None
    article: str | None = None
    paragraph: str | None = None
    inciso: str | None = None
    alinea: str | None = None
    text: str = Field(..., min_length=1)
    source_url: str | None = None
    version: str
    content_hash: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class LegalCitation(BaseModel):
    """A verifiable reference attached to an answer claim (§8)."""

    citation_id: str
    source: Source
    doc_type: DocType
    title: str
    source_url: str | None = None
    article: str | None = None
    case_number: str | None = None
    court: str | None = None
    judgment_date: date | None = None
    publication_date: date | None = None
    support_level: SupportLevel
    chunk_id: str | None = None


class CaseLawDocument(BaseModel):
    """A jurisprudential document (§8). ``doc_type`` is fixed to ``case_law``."""

    document_id: str
    doc_type: Literal[DocType.CASE_LAW] = DocType.CASE_LAW
    source: Source
    court: str
    case_number: str | None = None
    rapporteur: str | None = None
    panel: str | None = None
    judgment_date: date | None = None
    publication_date: date | None = None
    legal_area: LegalArea | None = None
    precedent_type: PrecedentType | None = None
    is_binding: bool = False
    ementa: str | None = None
    full_text: str | None = None
    source_url: str | None = None
    content_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)
