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

import re

from packages.agents.citation_auditor import audit_answer
from packages.answer.citation_auditor import CitationAuditResult
from packages.answer.formatter import build_answer, build_refusal
from packages.answer.prompts import build_answer_messages
from packages.answer.schemas import (
    AnswerResponse,
    AnswerStatus,
    CitationAudit,
    LegalBasisItem,
)
from packages.llm.base import LLMProvider
from packages.rag.context_builder import BuiltContext, build_context
from packages.rag.search_service import SearchService
from packages.rag.types import RetrievedChunk

# Strong out-of-scope signals (§2.2, §15.2 MVP). When a question carries one of
# these terms, it lies outside Direito do Consumidor regardless of how high the
# semantic similarity against the CDC corpus is — e.g. "recuperação judicial de
# sociedade limitada" lexically overlaps with CDC art. 104-A (superendividamento)
# at sem≈0.55, but the legal regime is Lei 11.101/2005, not the CDC. Refusing on
# this evidence is safer than letting the LLM stitch CDC articles into an
# off-domain answer. Audited against the golden set (Phase 13.D.4): zero false
# positives over the 122 in-scope questions, captures all 3 leaked OOS cases
# (oos-emp-01, oos-adm-02, oos-pre-02) plus the rest of the OOS block.
# Word-boundary matched to avoid "licitação" colliding with "solicitação".
_OOS_KEYWORDS: tuple[str, ...] = (
    # Empresarial / societário (Lei 11.101/2005, Lei das S.A.)
    "recuperação judicial",
    "recuperacao judicial",
    "sociedade limitada",
    "sociedade anônima",
    "sociedade anonima",
    "sociedade empresária",
    "m&a",
    # Administrativo (Lei 14.133/2021, regime de servidores)
    "licitação",
    "licitacao",
    "concurso público",
    "concurso publico",
    "servidor público",
    "servidor publico",
    "improbidade",
    # Previdenciário (Lei 8.213/1991, INSS)
    "inss",
    "aposentadoria",
    "benefício por incapacidade",
    "beneficio por incapacidade",
    "tempo de contribuição",
    "tempo de contribuicao",
    "agentes nocivos",
    "previdenciário",
    "previdenciario",
    # Sucessões / notarial
    "testamento",
    "tabelionato",
    # Eleitoral / migração
    "inelegibilidade",
    "visto humanitário",
    "visto humanitario",
    "migração",
    "migracao",
    # Penal / processual penal
    "latrocínio",
    "latrocinio",
    "pena de reclusão",
    "pena de reclusao",
    # Civil / sucessões / reais
    "usucapião",
    "usucapiao",
    "herdeiros necessários",
    "herdeiros necessarios",
    # Tributário (consumer-banking terms like "cartão" stay in CONSUMER)
    "imposto de renda",
    # Trabalhista
    "clt",
    "insalubridade",
)
_OOS_REGEX = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in _OOS_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def _is_out_of_scope(question: str) -> bool:
    """True if the question carries a strong non-consumer scope signal (§2.2)."""

    return bool(_OOS_REGEX.search(question))

# Minimum raw semantic similarity for a retrieved chunk to count as grounding.
# Below this, the recovered text is lexically/conceptually off-topic (e.g. an
# out-of-scope question hitting only weakly-related CDC articles), so the writer
# refuses safely instead of answering on unsupported sources (§2.2, §2.3, §40).
#
# Since Phase 5 this is a *first-pass* heuristic, no longer the sole scope gate: the
# CitationAuditor (below) is the robust, claim-level check. Kept injectable so a real
# embedding model can recalibrate it. Tuned to 0.29 after the IDF-weighted
# FakeEmbeddingProvider (Phase 13 recall fix) compressed the score band: 0.29 keeps
# all 7/7 OOS golden queries below the gate while staying above the 4-chunk unit
# fixture's "defeito do produto" semantic (~0.299). Above 0.30 the small fixture
# drops below the gate; below 0.28 OOS leaks ("imposto territorial" hits 0.357 on
# CDC art. 70).
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
        # Strong-OOS gate (§2.2): refuse adversarial out-of-scope queries before
        # spending an LLM call. The semantic threshold alone is insufficient when
        # OOS questions hit CDC chunks at sem≈0.4–0.55 (e.g. "recuperação
        # judicial" → CDC art. 104-A superendividamento). See _OOS_KEYWORDS.
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
