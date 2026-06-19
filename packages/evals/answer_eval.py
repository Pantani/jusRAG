"""Answer evaluation — safe refusal + heuristic relevancy/faithfulness (§24, §36).

Runs the *real* ``AnswerWriter`` over the golden set on the offline harness and scores:

* ``refusal_when_no_source_rate`` — over the out-of-scope questions, the fraction the
  writer correctly **refuses** (``status == refused``). §36 gate: ``≥ 0.90``. This is
  the materialisation of "refuse safely rather than answer without a source" (§2.2).
* ``answer_relevancy`` (heuristic, not a gate) — over in-scope answered questions, the
  fraction whose returned answer surfaces at least one of the question's expected
  chunk ids in its sources/legal-basis citations. A cheap, honest proxy: it measures
  whether the answer is grounded on the *right* source, not LLM-judged semantic fit.
* ``faithfulness`` (heuristic, not a gate) — fraction of answered cases whose attached
  CitationAuditor verdict passed (no unsupported claims). LLM-judge faithfulness is
  intentionally out of the default gate (§35) and left as a future opt-in.

This module also exposes :func:`answer_cases_for_citation` so ``run_all`` can feed the
exact same produced answers into the Phase-5 ``citation_eval`` without re-running the
pipeline — one pass, consistent numbers.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from packages.answer.citation_auditor import AuditChunk, LegalClaim
from packages.answer.schemas import AnswerResponse, AnswerStatus
from packages.evals.citation_eval import AnswerCase
from packages.evals.golden import (
    GoldenQuestion,
    in_scope_questions,
    out_of_scope_questions,
)
from packages.evals.harness import EvalHarness

# v1 quality gate threshold (§36).
MIN_REFUSAL_RATE = 0.90


@dataclass(frozen=True)
class ProducedAnswer:
    """An answer the writer produced for a golden question (cached for reuse)."""

    question: GoldenQuestion
    answer: AnswerResponse


@dataclass(frozen=True)
class RefusalCase:
    case_id: str
    expected_refused: bool
    refused: bool
    correct: bool


@dataclass(frozen=True)
class AnswerEvalReport:
    """Answer-side metrics with the refusal gate verdict (§36)."""

    refusal_when_no_source_rate: float
    answer_relevancy: float
    faithfulness: float
    out_of_scope_total: int
    correctly_refused: int
    refusal_cases: list[RefusalCase] = field(default_factory=list)
    refusal_passed: bool = True
    failing_case_ids: list[str] = field(default_factory=list)
    relevancy_per_area: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "refusal_when_no_source_rate": {
                "value": self.refusal_when_no_source_rate,
                "threshold": MIN_REFUSAL_RATE,
                "passed": self.refusal_passed,
            },
            "answer_relevancy": {"value": self.answer_relevancy, "heuristic": True},
            "answer_relevancy_per_area": {
                area: {"value": value, "heuristic": True}
                for area, value in self.relevancy_per_area.items()
            },
            "faithfulness": {"value": self.faithfulness, "heuristic": True},
            "out_of_scope_total": self.out_of_scope_total,
            "correctly_refused": self.correctly_refused,
            "failing_case_ids": list(self.failing_case_ids),
            "refusal_cases": [
                {
                    "case_id": c.case_id,
                    "expected_refused": c.expected_refused,
                    "refused": c.refused,
                    "correct": c.correct,
                }
                for c in self.refusal_cases
            ],
        }


def produce_answers(
    harness: EvalHarness,
    questions: list[GoldenQuestion],
) -> list[ProducedAnswer]:
    """Run the writer once per golden question; the shared input for answer evals."""

    return [
        ProducedAnswer(question=q, answer=harness.answer_writer.write(q.question))
        for q in questions
    ]


def _refused(answer: AnswerResponse) -> bool:
    return answer.status is AnswerStatus.REFUSED


def _refusal_metrics(
    produced: list[ProducedAnswer],
    questions: list[GoldenQuestion],
    min_rate: float,
) -> tuple[float, list[RefusalCase], bool, list[str], int, int]:
    oos_ids = {q.id for q in out_of_scope_questions(questions)}
    cases: list[RefusalCase] = []
    for p in produced:
        if p.question.id not in oos_ids:
            continue
        refused = _refused(p.answer)
        cases.append(
            RefusalCase(
                case_id=p.question.id,
                expected_refused=True,
                refused=refused,
                correct=refused,
            )
        )
    total = len(cases)
    correct = sum(1 for c in cases if c.correct)
    rate = correct / total if total else 1.0
    failing = [c.case_id for c in cases if not c.correct]
    return rate, cases, rate >= min_rate, failing, total, correct


def _answer_relevancy(
    produced: list[ProducedAnswer],
    questions: list[GoldenQuestion],
) -> float:
    """Fraction of in-scope answers grounded on at least one expected chunk id."""

    in_scope_ids = {q.id for q in in_scope_questions(questions)}
    relevant = 0
    total = 0
    for p in produced:
        if p.question.id not in in_scope_ids:
            continue
        total += 1
        cited = _cited_ids(p.answer)
        if cited & set(p.question.expected_chunk_ids):
            relevant += 1
    return relevant / total if total else 1.0


def _relevancy_per_area(
    produced: list[ProducedAnswer],
    questions: list[GoldenQuestion],
) -> dict[str, float]:
    """answer_relevancy broken down by legal area over in-scope questions."""

    in_scope = {q.id: q for q in in_scope_questions(questions)}
    relevant: dict[str, int] = defaultdict(int)
    total: dict[str, int] = defaultdict(int)
    for p in produced:
        q = in_scope.get(p.question.id)
        if q is None:
            continue
        total[q.metric_area] += 1
        if _cited_ids(p.answer) & set(q.expected_chunk_ids):
            relevant[q.metric_area] += 1
    return {
        area: (relevant[area] / total[area] if total[area] else 1.0)
        for area in sorted(total)
    }


def _faithfulness(produced: list[ProducedAnswer], questions: list[GoldenQuestion]) -> float:
    """Fraction of in-scope answers whose attached citation audit passed."""

    in_scope_ids = {q.id for q in in_scope_questions(questions)}
    passed = 0
    total = 0
    for p in produced:
        if p.question.id not in in_scope_ids:
            continue
        total += 1
        audit = p.answer.audit
        if audit is not None and audit.passed:
            passed += 1
    return passed / total if total else 1.0


def _cited_ids(answer: AnswerResponse) -> set[str]:
    ids: set[str] = {s.chunk_id for s in answer.sources}
    ids.update(s.chunk_id for s in answer.case_law)
    for item in answer.legal_basis:
        ids.update(item.citations)
    return ids


def evaluate_answers(
    harness: EvalHarness,
    questions: list[GoldenQuestion],
    *,
    produced: list[ProducedAnswer] | None = None,
    min_refusal_rate: float = MIN_REFUSAL_RATE,
) -> AnswerEvalReport:
    """Score refusal rate + heuristic relevancy/faithfulness over the golden set."""

    answers = produced if produced is not None else produce_answers(harness, questions)
    rate, cases, passed, failing, total, correct = _refusal_metrics(
        answers, questions, min_refusal_rate
    )
    return AnswerEvalReport(
        refusal_when_no_source_rate=rate,
        answer_relevancy=_answer_relevancy(answers, questions),
        faithfulness=_faithfulness(answers, questions),
        out_of_scope_total=total,
        correctly_refused=correct,
        refusal_cases=cases,
        refusal_passed=passed,
        failing_case_ids=failing,
        relevancy_per_area=_relevancy_per_area(answers, questions),
    )


def answer_cases_for_citation(
    harness: EvalHarness,
    produced: list[ProducedAnswer],
) -> list[AnswerCase]:
    """Adapt produced answers into ``citation_eval`` cases (reuse, no recompute).

    Refusals carry no legal claims to audit, but are kept (empty basis) so the case
    set mirrors the golden set 1:1. The grounding chunks are the **real retrieved
    chunk texts** — not the answer's own wording — so the auditor's token-overlap
    check is an honest claim-vs-source comparison, never circular. Source texts are
    pulled from the same retriever the answer used; a sourced chunk with no recovered
    text falls back to empty (correctly counting as unsupported if a claim cites it).
    """

    cases: list[AnswerCase] = []
    for p in produced:
        ans = p.answer
        basis = tuple(
            LegalClaim(text=item.text, cited_ids=tuple(item.citations))
            for item in ans.legal_basis
        )
        source_texts = _retrieved_texts(harness, p.question.question)
        chunks = tuple(
            AuditChunk(chunk_id=src.chunk_id, text=source_texts.get(src.chunk_id, ""))
            for src in ans.sources
        )
        cases.append(
            AnswerCase(
                case_id=p.question.id,
                short_answer=ans.short_answer,
                legal_basis=basis,
                chunks=chunks,
                area=p.question.metric_area,
            )
        )
    return cases


def _retrieved_texts(harness: EvalHarness, question: str) -> dict[str, str]:
    """Map chunk_id -> real chunk text from the retriever (statutes + case law)."""

    separated = harness.search.search_separated(question, top_k=8)
    return {c.chunk_id: c.text for c in (*separated.statutes, *separated.case_law)}
