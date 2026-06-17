"""Runtime agentic state — ``LegalResearchState`` (§13).

The single Pydantic state threaded through the LangGraph runtime (§14). Shape is
**exactly** §13: no extra fields, defaults via ``Field(default_factory=...)``,
``status`` a closed ``Literal``. Per-step traces are emitted out-of-band by the nodes
(structured logging in :mod:`packages.agents.graph`) so the state stays normative.

Each graph node is a plain function taking the state and returning a *partial* update
dict; LangGraph merges it. ``errors`` and ``caveats`` are accumulated across nodes via
the reducer-free convention of returning the full new list (nodes read current state,
append, and return). Kept free of LangGraph imports so every field is testable bare.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RetrievedSource(BaseModel):
    """A retrieved source threaded into the state (§13)."""

    chunk_id: str
    doc_type: str
    title: str
    text: str
    score: float
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CitationAuditResult(BaseModel):
    """Citation audit verdict carried in the state (§13)."""

    citation_coverage: float
    unsupported_claim_rate: float
    unsupported_claims: list[str] = Field(default_factory=list)
    passed: bool


class LegalResearchState(BaseModel):
    """End-to-end runtime state for the legal-research workflow (§13)."""

    run_id: str
    question: str
    jurisdiction: str = "BR"
    legal_area: str | None = None
    facts: dict[str, Any] = Field(default_factory=dict)
    missing_facts: list[str] = Field(default_factory=list)
    retrieved_statutes: list[RetrievedSource] = Field(default_factory=list)
    retrieved_case_law: list[RetrievedSource] = Field(default_factory=list)
    selected_context: list[RetrievedSource] = Field(default_factory=list)
    draft_answer: str | None = None
    final_answer: str | None = None
    caveats: list[str] = Field(default_factory=list)
    audit: CitationAuditResult | None = None
    status: Literal[
        "running", "needs_more_info", "answered", "refused", "failed"
    ] = "running"
    errors: list[str] = Field(default_factory=list)
