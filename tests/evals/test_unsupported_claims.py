"""Eval: simulated hallucination is detected and gates the build (§21, §36, §12.11).

This is the eval-side of Phase 5. It does not test the auditor's internals (that is
``tests/unit/answer/test_citation_auditor.py``); it proves the *aggregation + gate*
in :mod:`packages.evals.citation_eval`:

* answers that cite an article outside the recovered context are flagged as
  unsupported and surfaced per-case;
* ``unsupported_legal_claim_rate`` is computed (micro-averaged over the corpus);
* the gate FAILS when the rate exceeds 0.05 and PASSES when it stays ``<= 0.05``;
* ``citation_coverage`` carries its own ``>= 0.90`` threshold.

Fully offline and deterministic — fixed AnswerCases, no LLM, no network.
"""

from __future__ import annotations

from packages.answer.citation_auditor import AuditChunk, LegalClaim
from packages.evals.citation_eval import (
    MAX_UNSUPPORTED_LEGAL_CLAIM_RATE,
    MIN_CITATION_COVERAGE,
    AnswerCase,
    evaluate_citations,
)

# Seed context chunks (a slice of the CDC seed: arts. 12 and 49). Only these articles
# exist in the "recovered context"; anything else a claim cites is a hallucination.
_ART_12 = AuditChunk(
    chunk_id="cdc-8078-1990-art-12",
    text=(
        "Art. 12. O fabricante, o produtor, o construtor e o importador respondem "
        "independentemente da existencia de culpa pela reparacao dos danos causados "
        "por defeitos do produto."
    ),
)
_ART_49 = AuditChunk(
    chunk_id="cdc-8078-1990-art-49",
    text=(
        "Art. 49. O consumidor pode desistir do contrato no prazo de sete dias a "
        "contar da assinatura quando a contratacao ocorrer fora do estabelecimento "
        "comercial."
    ),
)
_CONTEXT = (_ART_12, _ART_49)


def _grounded_case(case_id: str) -> AnswerCase:
    """A well-grounded answer: every claim maps onto a recovered chunk."""

    return AnswerCase(
        case_id=case_id,
        short_answer="Segundo o art. 12, o fabricante responde independentemente de culpa.",
        legal_basis=(
            LegalClaim(
                text="O art. 12 do CDC fixa a responsabilidade por defeito do produto.",
                cited_ids=("cdc-8078-1990-art-12",),
            ),
        ),
        chunks=_CONTEXT,
    )


def _single_grounded_case(case_id: str) -> AnswerCase:
    """A well-grounded answer with exactly ONE auditable claim (no marker in summary)."""

    return AnswerCase(
        case_id=case_id,
        short_answer="Veja abaixo.",
        legal_basis=(
            LegalClaim(
                text="O art. 12 do CDC fixa a responsabilidade por defeito do produto.",
                cited_ids=("cdc-8078-1990-art-12",),
            ),
        ),
        chunks=_CONTEXT,
    )


def _hallucinated_case(case_id: str) -> AnswerCase:
    """An answer citing art. 999, never present in the recovered context."""

    return AnswerCase(
        case_id=case_id,
        short_answer="O art. 999 do CDC garante reembolso em dobro automatico.",
        legal_basis=(
            LegalClaim(
                text="O art. 999 do CDC assegura devolucao em dobro automatica.",
                cited_ids=("cdc-8078-1990-art-999",),
            ),
        ),
        chunks=_CONTEXT,
    )


def test_hallucinated_claim_is_detected_per_case() -> None:
    report = evaluate_citations([_hallucinated_case("c1")])

    case = report.cases[0]
    assert case.case_id == "c1"
    assert not case.passed
    # Both extracted claims (short_answer + legal_basis) cite the hallucinated art. 999.
    assert case.unsupported_legal_claim_rate == 1.0
    assert any("999" in claim for claim in case.unsupported_claims)


def test_unsupported_rate_is_micro_averaged() -> None:
    # Each case yields 2 claims (short_answer sentence + legal_basis). 3 grounded
    # (0 unsupported) + 1 hallucinated (2 unsupported) => 2/8 = 0.25.
    cases = [_grounded_case(f"g{i}") for i in range(3)] + [_hallucinated_case("h1")]
    report = evaluate_citations(cases)

    assert report.total_claims == 8
    assert report.total_unsupported == 2
    assert report.unsupported_legal_claim_rate == 0.25
    assert report.citation_coverage == 0.75


def test_gate_fails_when_rate_exceeds_threshold() -> None:
    # Half the corpus hallucinates => rate 0.5 > 0.05.
    cases = [_grounded_case("g1"), _hallucinated_case("h1")]
    report = evaluate_citations(cases)

    assert report.unsupported_legal_claim_rate > MAX_UNSUPPORTED_LEGAL_CLAIM_RATE
    assert not report.unsupported_passed
    assert not report.coverage_passed
    assert not report.passed
    assert "h1" in report.failing_case_ids
    assert "g1" not in report.failing_case_ids


def test_gate_passes_when_rate_within_threshold() -> None:
    # 20 grounded cases, 0 unsupported => rate 0.0 <= 0.05, coverage 1.0 >= 0.90.
    cases = [_grounded_case(f"g{i}") for i in range(20)]
    report = evaluate_citations(cases)

    assert report.unsupported_legal_claim_rate <= MAX_UNSUPPORTED_LEGAL_CLAIM_RATE
    assert report.citation_coverage >= MIN_CITATION_COVERAGE
    assert report.unsupported_passed
    assert report.coverage_passed
    assert report.passed
    assert report.failing_case_ids == []


def _single_unsupported_case(case_id: str) -> AnswerCase:
    """A case with exactly ONE auditable claim, and it is unsupported (art. 999).

    The ``short_answer`` is deliberately free of any legal marker/article so it is not
    extracted as a claim; only the single hallucinated ``legal_basis`` counts.
    """

    return AnswerCase(
        case_id=case_id,
        short_answer="Veja abaixo.",
        legal_basis=(
            LegalClaim(
                text="O art. 999 do CDC assegura devolucao em dobro automatica.",
                cited_ids=("cdc-8078-1990-art-999",),
            ),
        ),
        chunks=_CONTEXT,
    )


def test_gate_boundary_exactly_at_threshold_passes() -> None:
    # 1 unsupported claim out of 20 => rate 0.05, exactly the threshold (<=) holds.
    # Single-claim cases control the denominator precisely.
    grounded = [_single_grounded_case(f"g{i}") for i in range(19)]
    cases = grounded + [_single_unsupported_case("h1")]
    report = evaluate_citations(cases)

    assert report.total_claims == 20
    assert report.total_unsupported == 1
    assert report.unsupported_legal_claim_rate == MAX_UNSUPPORTED_LEGAL_CLAIM_RATE
    assert report.unsupported_passed
    # coverage 0.95 >= 0.90 also holds at this boundary.
    assert report.coverage_passed
    assert report.passed


def test_empty_corpus_is_vacuously_clean() -> None:
    report = evaluate_citations([])

    assert report.total_claims == 0
    assert report.citation_coverage == 1.0
    assert report.unsupported_legal_claim_rate == 0.0
    assert report.passed


def test_report_as_dict_carries_thresholds_and_failures() -> None:
    report = evaluate_citations([_grounded_case("g1"), _hallucinated_case("h1")])
    data = report.as_dict()

    assert data["unsupported_legal_claim_rate"]["threshold"] == (
        MAX_UNSUPPORTED_LEGAL_CLAIM_RATE
    )
    assert data["unsupported_legal_claim_rate"]["passed"] is False
    assert data["citation_coverage"]["threshold"] == MIN_CITATION_COVERAGE
    assert data["failing_case_ids"] == ["h1"]
    assert data["passed"] is False
