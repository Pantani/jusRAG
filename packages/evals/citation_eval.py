"""Citation evaluation — aggregate citation metrics over a set of answers (§36).

This is the *eval* layer for the citation/hallucination gate. It does **not**
reimplement the auditing logic: each answer is scored by the Phase-5
:func:`packages.answer.citation_auditor.audit_claims`, and this module aggregates the
per-answer ``CitationAuditResult`` into corpus-level metrics that Phase-8 ``run_all``
will orchestrate over the golden dataset.

Metrics produced (§36):

* ``citation_coverage`` — mean fraction of legal claims that are grounded;
* ``unsupported_legal_claim_rate`` — pooled (micro-averaged) fraction of unsupported
  claims across the whole corpus. Pooling, not a mean-of-rates, is the honest figure:
  one answer with many hallucinated claims is not diluted by many trivially-covered
  answers.

The threshold check materialises the build gate: ``unsupported_legal_claim_rate`` must
be ``<= 0.05``. ``citation_coverage`` carries its own ``>= 0.90`` threshold for the
report. Pure and offline — no LLM, no network — so it runs in CI with fake providers.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from packages.answer.citation_auditor import (
    AuditChunk,
    LegalClaim,
    audit_claims,
)

# v1 quality gate thresholds (§36).
MAX_UNSUPPORTED_LEGAL_CLAIM_RATE = 0.05
MIN_CITATION_COVERAGE = 0.90


@dataclass(frozen=True)
class AnswerCase:
    """One answer to audit: the draft answer plus the context it was grounded on.

    Mirrors the auditor's inputs so the eval reuses :func:`audit_claims` verbatim.
    ``case_id`` lets the report point at the exact failing golden question.
    """

    case_id: str
    short_answer: str
    legal_basis: tuple[LegalClaim, ...]
    chunks: tuple[AuditChunk, ...]
    area: str = "consumer"


@dataclass(frozen=True)
class CaseAudit:
    """Per-case audit result kept for drill-down in the report."""

    case_id: str
    area: str
    citation_coverage: float
    unsupported_legal_claim_rate: float
    unsupported_claims: list[str]
    total_claims: int
    passed: bool


@dataclass(frozen=True)
class CitationEvalReport:
    """Corpus-level citation metrics with per-threshold pass/fail (§36)."""

    citation_coverage: float
    unsupported_legal_claim_rate: float
    total_claims: int
    total_unsupported: int
    cases: list[CaseAudit] = field(default_factory=list)
    coverage_passed: bool = True
    unsupported_passed: bool = True
    failing_case_ids: list[str] = field(default_factory=list)
    per_area: dict[str, dict[str, float]] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Whole-suite verdict: every threshold must hold."""

        return self.coverage_passed and self.unsupported_passed

    def as_dict(self) -> dict[str, object]:
        return {
            "citation_coverage": {
                "value": self.citation_coverage,
                "threshold": MIN_CITATION_COVERAGE,
                "passed": self.coverage_passed,
            },
            "unsupported_legal_claim_rate": {
                "value": self.unsupported_legal_claim_rate,
                "threshold": MAX_UNSUPPORTED_LEGAL_CLAIM_RATE,
                "passed": self.unsupported_passed,
            },
            "total_claims": self.total_claims,
            "total_unsupported": self.total_unsupported,
            "passed": self.passed,
            "per_area": self.per_area,
            "failing_case_ids": list(self.failing_case_ids),
            "cases": [
                {
                    "case_id": c.case_id,
                    "area": c.area,
                    "citation_coverage": c.citation_coverage,
                    "unsupported_legal_claim_rate": c.unsupported_legal_claim_rate,
                    "total_claims": c.total_claims,
                    "unsupported_claims": list(c.unsupported_claims),
                    "passed": c.passed,
                }
                for c in self.cases
            ],
        }


def audit_case(
    case: AnswerCase,
    *,
    max_unsupported_rate: float = MAX_UNSUPPORTED_LEGAL_CLAIM_RATE,
) -> CaseAudit:
    """Score a single answer by reusing the Phase-5 auditor (no re-implementation)."""

    result = audit_claims(
        case.short_answer,
        list(case.legal_basis),
        list(case.chunks),
        max_unsupported_rate=max_unsupported_rate,
    )
    total_claims = _count_claims(case)
    return CaseAudit(
        case_id=case.case_id,
        area=case.area,
        citation_coverage=result.citation_coverage,
        unsupported_legal_claim_rate=result.unsupported_legal_claim_rate,
        unsupported_claims=list(result.unsupported_claims),
        total_claims=total_claims,
        passed=result.passed,
    )


def _per_area_citation(audits: list[CaseAudit]) -> dict[str, dict[str, float]]:
    """Micro-averaged coverage + unsupported rate per legal area."""

    claims: dict[str, int] = defaultdict(int)
    unsupported: dict[str, int] = defaultdict(int)
    for a in audits:
        claims[a.area] += a.total_claims
        unsupported[a.area] += len(a.unsupported_claims)
    out: dict[str, dict[str, float]] = {}
    for area in sorted(claims):
        total = claims[area]
        unsup = unsupported[area]
        rate = unsup / total if total else 0.0
        out[area] = {
            "citation_coverage": 1.0 - rate if total else 1.0,
            "unsupported_legal_claim_rate": rate,
            "total_claims": float(total),
        }
    return out


def _count_claims(case: AnswerCase) -> int:
    """Number of auditable claims for this case, via the auditor's own extractor."""

    from packages.answer.citation_auditor import extract_claims

    return len(extract_claims(case.short_answer, list(case.legal_basis)))


def evaluate_citations(
    cases: Iterable[AnswerCase],
    *,
    max_unsupported_rate: float = MAX_UNSUPPORTED_LEGAL_CLAIM_RATE,
    min_coverage: float = MIN_CITATION_COVERAGE,
) -> CitationEvalReport:
    """Aggregate per-case audits into corpus citation metrics with gate verdicts.

    ``unsupported_legal_claim_rate`` is micro-averaged (total unsupported claims over
    total claims) so a single heavily-hallucinated answer cannot be diluted. An empty
    corpus has nothing to flag: coverage 1.0, rate 0.0, both gates vacuously pass.
    """

    audits = [audit_case(c, max_unsupported_rate=max_unsupported_rate) for c in cases]

    total_claims = sum(a.total_claims for a in audits)
    total_unsupported = sum(len(a.unsupported_claims) for a in audits)

    if total_claims == 0:
        unsupported_rate = 0.0
        coverage = 1.0
    else:
        unsupported_rate = total_unsupported / total_claims
        coverage = 1.0 - unsupported_rate

    unsupported_passed = unsupported_rate <= max_unsupported_rate
    coverage_passed = coverage >= min_coverage
    failing = [a.case_id for a in audits if not a.passed]

    return CitationEvalReport(
        per_area=_per_area_citation(audits),
        citation_coverage=coverage,
        unsupported_legal_claim_rate=unsupported_rate,
        total_claims=total_claims,
        total_unsupported=total_unsupported,
        cases=audits,
        coverage_passed=coverage_passed,
        unsupported_passed=unsupported_passed,
        failing_case_ids=failing,
    )
