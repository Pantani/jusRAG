"""CitationAudit runtime node (§12.8, §15.7).

A thin, framework-free wrapper around :mod:`packages.answer.citation_auditor` that
adapts the answer/context shapes into the auditor's inputs and returns the §31
result. This is the *node* the Phase 7 LangGraph will call to thread the audit into
``LegalResearchState.audit``; here it is just a pure function — no LangGraph coupling
yet. Keeping it pure means the same call audits both a formatted ``AnswerResponse``
and the runtime state's selected context.
"""

from __future__ import annotations

from packages.answer.citation_auditor import (
    AuditChunk,
    CitationAuditResult,
    LegalClaim,
    audit_claims,
)
from packages.answer.schemas import AnswerResponse
from packages.rag.context_builder import BuiltContext


def _claims_from_answer(answer: AnswerResponse) -> list[LegalClaim]:
    return [
        LegalClaim(text=item.text, cited_ids=tuple(item.citations))
        for item in answer.legal_basis
    ]


def _chunks_from_context(context: BuiltContext) -> list[AuditChunk]:
    return [AuditChunk(chunk_id=c.chunk_id, text=c.text) for c in context.chunks]


def audit_answer(answer: AnswerResponse, context: BuiltContext) -> CitationAuditResult:
    """Audit a formatted answer against the context it was built from (§31)."""

    return audit_claims(
        answer.short_answer,
        _claims_from_answer(answer),
        _chunks_from_context(context),
    )


def run_citation_audit_node(
    answer: AnswerResponse,
    context: BuiltContext,
) -> CitationAuditResult:
    """Phase-7 graph node entrypoint (pure for now): audit and return the §31 result."""

    return audit_answer(answer, context)


# --- LangGraph node (Phase 7) -------------------------------------------------

from collections.abc import Callable  # noqa: E402
from typing import Any  # noqa: E402

from packages.agents.answer_writer import AnswerBuffer  # noqa: E402
from packages.agents.state import CitationAuditResult as StateAuditResult  # noqa: E402
from packages.agents.state import LegalResearchState  # noqa: E402


def to_state_audit(result: CitationAuditResult) -> StateAuditResult:
    """Map the §31 auditor result onto the §13 state's ``CitationAuditResult``.

    Note the field rename: §31 ``unsupported_legal_claim_rate`` → §13
    ``unsupported_claim_rate``. Values are carried verbatim.
    """

    return StateAuditResult(
        citation_coverage=result.citation_coverage,
        unsupported_claim_rate=result.unsupported_legal_claim_rate,
        unsupported_claims=list(result.unsupported_claims),
        passed=result.passed,
    )


def make_citation_auditor(
    buffer: AnswerBuffer,
) -> Callable[[LegalResearchState], dict[str, Any]]:
    """Build the ``audit_citations`` node bound to the per-run answer buffer (§15.7)."""

    def run_audit_citations(state: LegalResearchState) -> dict[str, Any]:
        answer = buffer.answer(state.run_id)
        context = buffer.context(state.run_id)
        if answer is None:
            return {"audit": None}
        result = audit_answer(answer, context)
        return {"audit": to_state_audit(result)}

    return run_audit_citations
