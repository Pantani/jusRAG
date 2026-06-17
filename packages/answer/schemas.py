"""Answer request/response shapes (§29 request, §30 AnswerWriter output).

The response is the normative structured shape: ``short_answer``, ``legal_basis[]``,
``case_law[]``, ``caveats[]``, ``sources[]``, ``not_legal_advice=true`` (always).
``legal_basis`` entries carry the supporting ``chunk_id`` citations; ``sources``
are derived from the retrieved chunks' ``CitationRef`` (chunk_id, article,
source_url). ``status`` makes a safe refusal explicit (§2.2, §40).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AnswerStatus(StrEnum):
    """Outcome of an answer attempt."""

    ANSWERED = "answered"
    REFUSED = "refused"


class AnswerRequest(BaseModel):
    """Wire request for POST /ask."""

    question: str = Field(..., min_length=1)
    top_k: int = Field(default=8, ge=1, le=50)
    filters: dict[str, Any] | None = None


class LegalBasisItem(BaseModel):
    """A legislation-grounded statement and the chunk ids that support it."""

    text: str
    citations: list[str]


class CaseLawItem(BaseModel):
    """A retrieved jurisprudence citation, kept separate from legislation (§2.3, §32).

    Populated *only* from actually retrieved case-law sources (``source_url`` from the
    indexed chunk). Never fabricated: when no jurisprudence is recovered the answer
    omits this block entirely (§22).
    """

    chunk_id: str
    court: str | None = None
    case_number: str | None = None
    title: str
    ementa: str
    source_url: str | None = None


class SourceItem(BaseModel):
    """A consulted source, derived from a retrieved chunk's citation (§30)."""

    chunk_id: str
    title: str
    article: str | None = None
    source_url: str | None = None
    doc_type: str
    source: str


class CitationAudit(BaseModel):
    """CitationAuditor result attached to the answer (§31, §13.audit)."""

    citation_coverage: float
    unsupported_legal_claim_rate: float
    unsupported_claims: list[str] = Field(default_factory=list)
    passed: bool


class AnswerResponse(BaseModel):
    """Structured legal answer (§30). ``not_legal_advice`` is always true (§2.6, §41)."""

    status: AnswerStatus
    short_answer: str
    legal_basis: list[LegalBasisItem] = Field(default_factory=list)
    case_law: list[CaseLawItem] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    sources: list[SourceItem] = Field(default_factory=list)
    not_legal_advice: Literal[True] = True
    audit: CitationAudit | None = None
