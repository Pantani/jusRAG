"""run_all tests (§24, §36): suite aggregates all metrics, report written, gate fires."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from packages.evals import run_all
from packages.evals.answer_eval import AnswerEvalReport
from packages.evals.citation_eval import CitationEvalReport
from packages.evals.golden import GoldenStats
from packages.evals.retrieval_eval import RetrievalEvalReport
from packages.evals.run_all import (
    MIN_GOLDEN,
    EvalSuiteResult,
    run_suite,
    write_reports,
)


def test_suite_passes_gate_on_seed() -> None:
    result = run_suite()
    assert result.golden.total >= MIN_GOLDEN
    assert result.gate_passed(strict=True)
    # All four §36 metrics are present and computed.
    assert result.retrieval.recall_at_k >= 0.80
    assert result.citation.citation_coverage >= 0.90
    assert result.citation.unsupported_legal_claim_rate <= 0.05
    assert result.answer.refusal_when_no_source_rate >= 0.90


def test_main_exits_zero_on_seed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(run_all, "_GENERATED", tmp_path)
    monkeypatch.setattr(run_all, "REPORT_JSON", tmp_path / "eval_report.json")
    monkeypatch.setattr(run_all, "REPORT_MD", tmp_path / "eval_report.md")
    assert run_all.main() == 0
    assert (tmp_path / "eval_report.json").exists()
    assert (tmp_path / "eval_report.md").exists()


def test_report_written_with_all_metrics(tmp_path: Path) -> None:
    result = run_suite()
    payload = result.as_dict(strict=True)
    json_path = tmp_path / "r.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False))
    metrics = payload["metrics"]
    assert "retrieval_recall_at_5" in metrics["retrieval"]
    assert "citation_coverage" in metrics["citation"]
    assert "unsupported_legal_claim_rate" in metrics["citation"]
    assert "refusal_when_no_source_rate" in metrics["answer"]


def test_gate_fails_on_unsupported_claim_violation() -> None:
    """The always-on hallucination gate fires even in non-strict mode (§2.1, §36)."""

    result = _violated_suite("citation_unsupported")
    assert not result.gate_passed(strict=False)
    assert not result.gate_passed(strict=True)


def test_strict_gate_fails_on_recall_violation_only_in_strict() -> None:
    result = _violated_suite("retrieval_recall")
    assert result.gate_passed(strict=False)  # not the hallucination gate
    assert not result.gate_passed(strict=True)


def test_strict_gate_fails_on_refusal_violation_only_in_strict() -> None:
    result = _violated_suite("refusal")
    assert result.gate_passed(strict=False)
    assert not result.gate_passed(strict=True)


def _violated_suite(kind: str) -> EvalSuiteResult:
    base = run_suite()
    if kind == "citation_unsupported":
        citation = replace(
            base.citation,
            unsupported_legal_claim_rate=0.50,
            unsupported_passed=False,
            coverage_passed=False,
            citation_coverage=0.50,
        )
        return _with(base, citation=citation)
    if kind == "retrieval_recall":
        retrieval = replace(base.retrieval, recall_at_k=0.10, recall_passed=False)
        return _with(base, retrieval=retrieval)
    if kind == "refusal":
        answer = replace(
            base.answer,
            refusal_when_no_source_rate=0.10,
            refusal_passed=False,
        )
        return _with(base, answer=answer)
    raise AssertionError(kind)


def _with(
    base: EvalSuiteResult,
    *,
    retrieval: RetrievalEvalReport | None = None,
    citation: CitationEvalReport | None = None,
    answer: AnswerEvalReport | None = None,
    golden: GoldenStats | None = None,
) -> EvalSuiteResult:
    return EvalSuiteResult(
        golden=golden or base.golden,
        retrieval=retrieval or base.retrieval,
        citation=citation or base.citation,
        answer=answer or base.answer,
    )


def test_write_reports_creates_both_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_all, "_GENERATED", tmp_path)
    monkeypatch.setattr(run_all, "REPORT_JSON", tmp_path / "eval_report.json")
    monkeypatch.setattr(run_all, "REPORT_MD", tmp_path / "eval_report.md")
    write_reports(run_suite(), strict=True)
    assert (tmp_path / "eval_report.json").exists()
    assert (tmp_path / "eval_report.md").exists()
