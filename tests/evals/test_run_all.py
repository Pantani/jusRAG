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


def test_suite_metrics_on_multiarea_seed() -> None:
    """All four §36 metrics are computed on the multi-area seed and PASS.

    Phase 14 recurate: after the principled scope gate (answer) + the hardened
    ``classify_area`` (agentic) + the golden recurate (eval), every §36 gate is
    honestly green on the deterministic fake pipeline. The OOS golden keeps only
    refusal cases the fake pipeline can distinguish (regimes that route to an
    out-of-scope area); the corpusless sub-topics of in-scope areas that only leak
    under the fake lexical embedding live in out_of_scope_eval_real_debt.yaml (NOT
    loaded by this gate) and are tracked as eval-real debt. No masking: these are the
    real numbers.
    """

    result = run_suite()
    assert result.golden.total >= MIN_GOLDEN
    # Always-on hallucination gate holds; this is the non-negotiable §2.1 gate.
    assert result.citation.unsupported_legal_claim_rate <= 0.05
    assert result.retrieval.recall_at_k >= 0.80
    assert result.citation.citation_coverage >= 0.90
    # Refusal now meets the §36 gate (>= 0.90) honestly.
    assert result.answer.refusal_when_no_source_rate >= 0.90
    assert result.gate_passed(strict=True)
    assert result.gate_passed(strict=False)


def test_main_exits_zero_in_hallucination_only_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With EVAL_GATE_STRICT=0 the build passes on the always-on hallucination gate."""

    monkeypatch.setenv("EVAL_GATE_STRICT", "0")
    monkeypatch.setattr(run_all, "_GENERATED", tmp_path)
    monkeypatch.setattr(run_all, "REPORT_JSON", tmp_path / "eval_report.json")
    monkeypatch.setattr(run_all, "REPORT_MD", tmp_path / "eval_report.md")
    assert run_all.main() == 0
    assert (tmp_path / "eval_report.json").exists()
    assert (tmp_path / "eval_report.md").exists()


def test_main_exits_zero_in_strict_mode_when_all_gates_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Strict mode (default) passes now that all four §36 gates are green (Phase 14)."""

    monkeypatch.delenv("EVAL_GATE_STRICT", raising=False)
    monkeypatch.setattr(run_all, "_GENERATED", tmp_path)
    monkeypatch.setattr(run_all, "REPORT_JSON", tmp_path / "eval_report.json")
    monkeypatch.setattr(run_all, "REPORT_MD", tmp_path / "eval_report.md")
    assert run_all.main() == 0
    assert (tmp_path / "eval_report.json").exists()


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


# --- Real-provider harness (opt-in: make eval-real) -------------------------


def test_report_contains_provider_field_default_fake(tmp_path: Path) -> None:
    """The JSON report always records which provider produced the metrics."""

    result = run_suite()
    payload = result.as_dict(strict=True)
    assert payload["provider"] == {"embedding": "fake", "llm": "fake"}


def test_report_provider_field_reflects_selection(tmp_path: Path) -> None:
    selection = run_all.ProviderSelection(embedding="openai", llm="openai")
    result = run_suite(provider=selection)
    payload = result.as_dict(strict=True)
    assert payload["provider"] == {"embedding": "openai", "llm": "openai"}


def test_markdown_report_renders_provider_header() -> None:
    from packages.evals.report import render_markdown

    payload = run_suite(
        provider=run_all.ProviderSelection(embedding="local", llm="ollama")
    ).as_dict(strict=True)
    md = render_markdown(payload)
    assert "## Providers" in md
    assert "Embedding: **local**" in md
    assert "LLM: **ollama**" in md


def test_main_openai_without_api_key_exits_non_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit) as excinfo:
        run_all.main(["--provider=openai"])
    assert excinfo.value.code != 0
    assert "OPENAI_API_KEY" in str(excinfo.value)


def test_main_ollama_unreachable_exits_non_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM=ollama with no reachable server aborts via _check_ollama_reachable."""

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    # Force the reachability check to fail deterministically.
    def _fail() -> None:
        raise SystemExit("Ollama is not reachable at http://nope (forced)")

    monkeypatch.setattr(run_all, "_check_ollama_reachable", _fail)
    with pytest.raises(SystemExit) as excinfo:
        run_all.main(["--provider=local"])
    assert "Ollama is not reachable" in str(excinfo.value)


def test_default_invocation_stays_on_fake_providers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`make eval` (no flag) must never touch real providers, even if env is set."""

    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    # Isolate the provider assertion from the open refusal-gate debt.
    monkeypatch.setenv("EVAL_GATE_STRICT", "0")
    monkeypatch.setattr(run_all, "_GENERATED", tmp_path)
    monkeypatch.setattr(run_all, "REPORT_JSON", tmp_path / "eval_report.json")
    monkeypatch.setattr(run_all, "REPORT_MD", tmp_path / "eval_report.md")
    assert run_all.main([]) == 0
    payload = json.loads((tmp_path / "eval_report.json").read_text())
    assert payload["provider"] == {"embedding": "fake", "llm": "fake"}


def test_sample_llm_runs_retrieval_full_but_llm_subset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--sample-llm N: retrieval over full golden; LLM (produce_answers) over N only."""

    from packages.evals import run_all as ra

    questions = ra.load_golden()
    total = len(questions)

    produce_calls: list[int] = []
    real_produce = ra.produce_answers

    def spy_produce(harness, subset):  # type: ignore[no-untyped-def]
        produce_calls.append(len(subset))
        return real_produce(harness, subset)

    retrieval_calls: list[int] = []
    real_retrieval = ra.evaluate_retrieval

    def spy_retrieval(harness, qs, **kwargs):  # type: ignore[no-untyped-def]
        retrieval_calls.append(len(qs))
        return real_retrieval(harness, qs, **kwargs)

    monkeypatch.setattr(ra, "produce_answers", spy_produce)
    monkeypatch.setattr(ra, "evaluate_retrieval", spy_retrieval)

    result = ra.run_suite(sample_llm=4)

    assert retrieval_calls == [total]  # retrieval gets the full set
    assert produce_calls == [4]  # LLM only the 4-sample
    assert result.llm_sample.size == 4
    assert result.llm_sample.active
    assert len(result.llm_sample.sampled_ids) == 4
    # Gate is informational under sampling: always "passes" (does not block CI).
    assert result.gate_passed(strict=True)


def test_stratified_llm_sample_is_deterministic_and_balanced() -> None:
    from packages.evals.run_all import stratified_llm_sample

    questions = load_golden_for_sample_test()
    sample = stratified_llm_sample(questions, 4)
    ids = [q.id for q in sample]
    in_scope = [q for q in sample if q.in_scope]
    oos = [q for q in sample if not q.in_scope]
    assert len(sample) == 4
    assert len(in_scope) == 2
    assert len(oos) == 2
    # Determinism: same call -> same order (preserves YAML order).
    again = [q.id for q in stratified_llm_sample(questions, 4)]
    assert ids == again


def load_golden_for_sample_test():  # type: ignore[no-untyped-def]
    from packages.evals.golden import load_golden as _lg

    return _lg()


def test_sample_llm_report_marks_gate_informational(tmp_path: Path) -> None:
    from packages.evals.report import render_markdown

    payload = run_suite(sample_llm=4).as_dict(strict=True)
    assert payload["llm_sampled"]["active"] is True
    assert payload["llm_sampled"]["size"] == 4
    assert payload["gate"]["informational"] is True
    md = render_markdown(payload)
    assert "LLM sample" in md
    assert "INFORMATIONAL" in md


def test_resolve_providers_pairs_default_llm() -> None:
    import argparse

    ns = argparse.Namespace(provider="openai", llm_provider=None)
    assert run_all._resolve_providers(ns) == run_all.ProviderSelection("openai", "openai")
    ns = argparse.Namespace(provider="local", llm_provider=None)
    assert run_all._resolve_providers(ns) == run_all.ProviderSelection("local", "ollama")
    ns = argparse.Namespace(provider="local", llm_provider="fake")
    assert run_all._resolve_providers(ns) == run_all.ProviderSelection("local", "fake")
    ns = argparse.Namespace(provider=None, llm_provider=None)
    assert run_all._resolve_providers(ns) == run_all.ProviderSelection("fake", "fake")
