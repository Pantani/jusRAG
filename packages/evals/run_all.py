"""Eval orchestrator + build gate (§24, §36). Entry point for ``make eval``.

Builds the offline harness, runs the three eval families over the golden dataset in a
single pass, aggregates every §36 metric, writes a JSON + Markdown report, prints a
summary, and **fails the build** (non-zero exit) when a gate threshold is violated.

Gate semantics (§36, and the rule "make eval may fail the build"):

* The hallucination gate is *always* enforced: ``unsupported_legal_claim_rate > 0.05``
  exits non-zero. This is the non-negotiable "don't hallucinate" gate (§2.1).
* The remaining §36 thresholds — ``retrieval_recall_at_5 ≥ 0.80``,
  ``citation_coverage ≥ 0.90``, ``refusal_when_no_source_rate ≥ 0.90`` — are enforced
  by default too, so a regression in any of them breaks CI. Set ``EVAL_GATE_STRICT=0``
  to enforce *only* the hallucination gate (e.g. while a dependent module is being
  fixed); the report still records every pass/fail regardless.

Fully offline (fake providers) — safe to run in CI with no network.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.evals.answer_eval import (
    AnswerEvalReport,
    answer_cases_for_citation,
    evaluate_answers,
    produce_answers,
)
from packages.evals.citation_eval import CitationEvalReport, evaluate_citations
from packages.evals.golden import GoldenStats, golden_stats, load_golden
from packages.evals.harness import EvalHarness, build_harness
from packages.evals.report import render_markdown
from packages.evals.retrieval_eval import RetrievalEvalReport, evaluate_retrieval

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GENERATED = _REPO_ROOT / "data" / "generated"
REPORT_JSON = _GENERATED / "eval_report.json"
REPORT_MD = _GENERATED / "eval_report.md"

MIN_GOLDEN = 30


@dataclass(frozen=True)
class EvalSuiteResult:
    """The full aggregated suite: every §36 metric + headcount + gate verdict."""

    golden: GoldenStats
    retrieval: RetrievalEvalReport
    citation: CitationEvalReport
    answer: AnswerEvalReport

    @property
    def gate_checks(self) -> list[tuple[str, bool, bool]]:
        """(name, passed, always_enforced) for each §36 gate."""

        return [
            ("retrieval_recall_at_5", self.retrieval.recall_passed, False),
            ("citation_coverage", self.citation.coverage_passed, False),
            ("unsupported_legal_claim_rate", self.citation.unsupported_passed, True),
            ("refusal_when_no_source_rate", self.answer.refusal_passed, False),
        ]

    def gate_passed(self, *, strict: bool) -> bool:
        """Build verdict. Strict: every gate. Non-strict: only the hallucination gate."""

        return all(
            passed for _, passed, always in self.gate_checks if strict or always
        )

    def as_dict(self, *, strict: bool) -> dict[str, Any]:
        return {
            "golden": {
                "total": self.golden.total,
                "in_scope": self.golden.in_scope,
                "out_of_scope": self.golden.out_of_scope,
                "min_required": MIN_GOLDEN,
                "meets_minimum": self.golden.total >= MIN_GOLDEN,
            },
            "gate": {
                "strict": strict,
                "passed": self.gate_passed(strict=strict),
                "checks": [
                    {"metric": name, "passed": passed, "always_enforced": always}
                    for name, passed, always in self.gate_checks
                ],
            },
            "metrics": {
                "retrieval": self.retrieval.as_dict(),
                "citation": self.citation.as_dict(),
                "answer": self.answer.as_dict(),
            },
        }


def run_suite(harness: EvalHarness | None = None) -> EvalSuiteResult:
    """Run every eval over the golden set in a single pipeline pass."""

    harness = harness or build_harness()
    questions = load_golden()

    retrieval = evaluate_retrieval(harness, questions)
    produced = produce_answers(harness, questions)
    answer = evaluate_answers(harness, questions, produced=produced)
    citation = evaluate_citations(answer_cases_for_citation(harness, produced))

    return EvalSuiteResult(
        golden=golden_stats(questions),
        retrieval=retrieval,
        citation=citation,
        answer=answer,
    )


def write_reports(result: EvalSuiteResult, *, strict: bool) -> None:
    _GENERATED.mkdir(parents=True, exist_ok=True)
    payload = result.as_dict(strict=strict)
    REPORT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    REPORT_MD.write_text(render_markdown(payload), encoding="utf-8")


def _print_summary(result: EvalSuiteResult, *, strict: bool) -> None:
    g = result.golden
    print(f"Golden questions: {g.total} (in-scope {g.in_scope}, out-of-scope {g.out_of_scope})")
    ret, cit, ans = result.retrieval, result.citation, result.answer
    rows = [
        ("retrieval_recall_at_5", ret.recall_at_k, 0.80, ret.recall_passed),
        ("citation_coverage", cit.citation_coverage, 0.90, cit.coverage_passed),
        (
            "unsupported_legal_claim_rate",
            cit.unsupported_legal_claim_rate,
            0.05,
            cit.unsupported_passed,
        ),
        ("refusal_when_no_source_rate", ans.refusal_when_no_source_rate, 0.90, ans.refusal_passed),
    ]
    for name, value, threshold, passed in rows:
        mark = "PASS" if passed else "FAIL"
        print(f"  [{mark}] {name} = {value:.4f} (threshold {threshold})")
    verdict = "PASSED" if result.gate_passed(strict=strict) else "FAILED"
    mode = "strict" if strict else "hallucination-only"
    print(f"Gate ({mode}): {verdict}")
    print(f"Report: {REPORT_JSON} | {REPORT_MD}")


def _strict_mode() -> bool:
    return os.environ.get("EVAL_GATE_STRICT", "1") != "0"


def main() -> int:
    strict = _strict_mode()
    result = run_suite()
    write_reports(result, strict=strict)
    _print_summary(result, strict=strict)
    if result.golden.total < MIN_GOLDEN:
        print(f"FAILED: golden set has {result.golden.total} questions, need >= {MIN_GOLDEN}.")
        return 1
    return 0 if result.gate_passed(strict=strict) else 1


if __name__ == "__main__":
    sys.exit(main())
