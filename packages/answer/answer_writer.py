"""AnswerWriter — orchestrates retrieve -> context -> LLM -> format -> audit (§30, §31).

Pipeline: retrieve ranked chunks via the ``SearchService``, build the source-labeled
context (``context_builder``, owned by rag), prompt the ``LLMProvider`` for a grounded
draft, format it into the structured ``AnswerResponse``, then run the CitationAuditor
(§31) and act on its verdict. Safe refusal (§2.2, §2.3, §40) is enforced at three
points: when retrieval returns no chunk, when the LLM signals ``refused``, and — the
robust gate added in Phase 5 — when auditing the draft finds legal claims the context
does not support. In that case the writer first rewrites conservatively (drops the
unsupported legal-basis statements); if too little supported basis survives, it
refuses rather than answer on shaky ground. The audit result is always attached to the
response (``audit``). Depends only on the ``SearchService`` and the ``LLMProvider``
Protocol, so fakes drive it offline.
"""

from __future__ import annotations

from packages.agents.citation_auditor import audit_answer
from packages.agents.classify_area import (
    classify_area,
    is_in_scope,
    matched_out_of_scope_regime,
)
from packages.answer.citation_auditor import CitationAuditResult
from packages.answer.formatter import build_answer, build_refusal
from packages.answer.prompts import build_answer_messages
from packages.answer.schemas import (
    AnswerResponse,
    AnswerStatus,
    CitationAudit,
    LegalBasisItem,
)
from packages.legal_types.enums import LegalArea
from packages.llm.base import LLMProvider
from packages.rag.context_builder import BuiltContext, build_context
from packages.rag.search_service import SearchService
from packages.rag.types import RetrievedChunk


# Scope gate (§2.2, §15.2). A prior phase used a closed list of out-of-scope keyword
# strings here; QA (_workspace/14_qa_multiarea_report.md) proved it overfit the golden
# and broke both ways — it refused in-scope questions that merely contained an ambiguous
# token (`clt`, `usucapião`, `icms`, "pena de reclusão" — including two criminal golden
# questions that have real corpus) and let unseen OOS regimes (marca/INPI, ambiental,
# LGPD) answer with spurious sources. A string list cannot generalize: it only refuses
# what it already enumerates, and any enumerated stem collides with the in-scope areas.
#
# The principled signal is area classification + absence of corpus, reusing the agentic
# area classifier (packages/agents/classify_area.py — a pure, deterministic, importable
# function with a general taxonomy, not tuned to the golden).
#
# CRITICAL (CodeRabbit #3): classify_area collapses TWO distinct cases into UNKNOWN:
#   (a) a corpus-less regime matched by a discriminant out-of-scope term (previdência,
#       INSS, falência, INPI, ambiental, ...) — genuinely out of scope; and
#   (b) NO keyword evidence at all — an in-corpus question the keyword map simply did
#       not recognize (e.g. an "inventário"/"usucapião" phrasing that misses the stems).
# At the LegalArea level these are indistinguishable, so a UNKNOWN-only gate had to choose
# between leaking (a) or pre-refusing (b). The agentic node now exposes the missing signal
# (_workspace/14_agentic_oos_signal_summary.md): matched_out_of_scope_regime(question) is
# True for (a) and False for (b), letting us decide each correctly.
#
# Gate logic:
#   - matched_out_of_scope_regime → True: deterministic §2.2 pre-refusal. A corpus-less
#     regime was explicitly matched; refuse before retrieval, independent of the embedding
#     provider (fixes the §2.2 leak where INPI/ambiental/previdenciário answered with
#     spurious FakeEmbedding sources).
#   - UNKNOWN with no regime match → proceed to retrieval. The researcher-node contract
#     (§14/§15.2) skips the legal_area filter for UNKNOWN precisely so a real source can
#     still surface; safe refusal then happens downstream when retrieval yields no grounded
#     source or the CitationAuditor (§31) rejects unsupported claims (fixes the in-corpus
#     false-negative on "inventário"/"usucapião" phrasings the keyword map misses).
#   - A defined area outside IN_SCOPE_AREAS (administrative) → refuse here. (administrative
#     also matches the regime check, so this is belt-and-suspenders.)
#
# This does NOT loosen §2.2: it splits the UNKNOWN decision on an explicit deterministic
# signal instead of a blind keyword gate. Contract dependency documented in CONTRACTS.md:
# answer imports classify_area, is_in_scope and matched_out_of_scope_regime (all pure,
# importable) plus LegalArea from agentic/legal_types.
def _is_out_of_scope(question: str) -> bool:
    """Refuse matched corpus-less regimes; let no-evidence UNKNOWN proceed (§2.2)."""

    if matched_out_of_scope_regime(question):
        # Corpus-less regime explicitly matched → deterministic §2.2 pre-refusal.
        return True
    area = classify_area(question)
    if area is LegalArea.UNKNOWN:
        # No evidence: let retrieval/auditor decide grounding, not a keyword pre-gate.
        return False
    return not is_in_scope(area)

# Minimum raw semantic similarity for a retrieved chunk to count as grounding.
# Below this, the recovered text is lexically/conceptually off-topic (e.g. an
# out-of-scope question hitting only weakly-related CDC articles), so the writer
# refuses safely instead of answering on unsupported sources (§2.2, §2.3, §40).
#
# Since Phase 5 this is a *first-pass* heuristic, no longer the sole scope gate: the
# area-scope classifier (above) is the regime-level check and the CitationAuditor (below)
# is the robust claim-level check. Kept injectable so a real embedding model can
# recalibrate it. Held at 0.29 in the multi-area corpus: it keeps all in-scope questions
# grounded while staying above the 4-chunk unit fixture's "defeito do produto" semantic
# (~0.299). OOS separation is done by area class, not by this absolute threshold — a grid
# sweep over the golden showed in-scope (min 0.310) and OOS (max 0.425) top1 scores
# overlap, so no global threshold separates them without a recall regression.
#
# Eval-real debt: with real (dense) embeddings the in-scope/OOS bands separate, so the
# optimal grounding point is *not* 0.29 and the keyword classifier becomes a backstop
# rather than the primary gate. Recalibrate against `make eval-real` once credentials
# exist; the threshold stays injectable precisely for that.
_MIN_SEMANTIC_SCORE = 0.29

# After conservatively dropping unsupported claims, the answer must keep at least one
# supported legal-basis statement; otherwise there is nothing left to stand on and the
# writer refuses (§2.2, §40).
_MIN_SUPPORTED_BASIS = 1


class AnswerWriter:
    """Produces a cited, audited, structured legal answer or a safe refusal."""

    def __init__(
        self,
        search_service: SearchService,
        llm: LLMProvider,
        min_semantic_score: float = _MIN_SEMANTIC_SCORE,
    ) -> None:
        self._search = search_service
        self._llm = llm
        self._min_semantic_score = min_semantic_score

    def write(
        self,
        question: str,
        top_k: int = 8,
        filters: dict[str, object] | None = None,
    ) -> AnswerResponse:
        # Area-scope gate (§2.2): refuse before spending an LLM call only when the
        # question classifies to a *defined* out-of-scope area (administrative). UNKNOWN
        # and in-scope areas proceed; grounding is decided by retrieval (_grounded) and
        # the auditor, not by a keyword pre-gate. See _is_out_of_scope note above.
        if _is_out_of_scope(question):
            return build_refusal(BuiltContext(text="", citations=[], chunks=[]))

        separated = self._search.search_separated(question, top_k, dict(filters or {}))
        grounded_statutes = self._grounded(separated.statutes)
        grounded_case_law = self._grounded(separated.case_law)

        # Scope gate (§2.2): refuse only when *no* source — neither legislation nor
        # jurisprudence — is in scope. A question whose answer rests on a retrieved
        # súmula still has a basis and must not be refused as out-of-scope.
        if not grounded_statutes and not grounded_case_law:
            return build_refusal(BuiltContext(text="", citations=[], chunks=[]))

        # The LLM and auditor see legislation *and* jurisprudence, so a hallucinated
        # súmula outside this context is caught by the audit (§2.1, §31). Legislation
        # is ordered first so legal_basis leads with statute grounding.
        context = build_context(grounded_statutes + grounded_case_law)
        messages = build_answer_messages(question, context)
        draft = self._llm.generate_answer(messages, context)
        answer = build_answer(draft, context, grounded_case_law)
        if answer.status is AnswerStatus.REFUSED:
            return answer
        return self._audit_and_enforce(answer, context)

    def _audit_and_enforce(
        self,
        answer: AnswerResponse,
        context: BuiltContext,
    ) -> AnswerResponse:
        """Run the §31 audit; rewrite conservatively or refuse on unsupported claims."""

        audit = audit_answer(answer, context)
        if audit.passed:
            # Empty-basis hedge guard (§2.2): a passing audit on zero claims means
            # the LLM produced a hedged short_answer without any legal basis — the
            # answer has nothing to stand on. Refuse rather than ship prose that
            # the eval (and the user) cannot distinguish from a grounded answer.
            if len(answer.legal_basis) < _MIN_SUPPORTED_BASIS:
                return self._refuse_with_audit(context, audit)
            return answer.model_copy(update={"audit": _to_schema(audit)})

        rewritten = self._drop_unsupported(answer, audit)
        if len(rewritten.legal_basis) < _MIN_SUPPORTED_BASIS:
            return self._refuse_with_audit(context, audit)

        # Re-audit the conservative rewrite so the attached metrics describe the
        # answer actually returned, not the discarded draft.
        final_audit = audit_answer(rewritten, context)
        if not final_audit.passed:
            return self._refuse_with_audit(context, final_audit)
        return rewritten.model_copy(update={"audit": _to_schema(final_audit)})

    @staticmethod
    def _drop_unsupported(
        answer: AnswerResponse,
        audit: CitationAuditResult,
    ) -> AnswerResponse:
        unsupported = set(audit.unsupported_claims)
        kept: list[LegalBasisItem] = [
            item for item in answer.legal_basis if item.text not in unsupported
        ]
        short = answer.short_answer
        if short in unsupported:
            short = kept[0].text if kept else short
        return answer.model_copy(update={"legal_basis": kept, "short_answer": short})

    @staticmethod
    def _refuse_with_audit(
        context: BuiltContext,
        audit: CitationAuditResult,
    ) -> AnswerResponse:
        refusal = build_refusal(context)
        return refusal.model_copy(update={"audit": _to_schema(audit)})

    def _grounded(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        return [c for c in chunks if c.semantic_score >= self._min_semantic_score]


def _to_schema(audit: CitationAuditResult) -> CitationAudit:
    return CitationAudit(
        citation_coverage=audit.citation_coverage,
        unsupported_legal_claim_rate=audit.unsupported_legal_claim_rate,
        unsupported_claims=list(audit.unsupported_claims),
        passed=audit.passed,
    )
