"""Retrieval eval tests (§24, §36): recall/precision computed, gate threshold honored."""

from __future__ import annotations

from packages.evals.golden import GoldenQuestion
from packages.evals.harness import build_harness
from packages.evals.retrieval_eval import MIN_RECALL_AT_5, evaluate_retrieval


def test_recall_at_5_meets_threshold_on_seed() -> None:
    report = evaluate_retrieval(build_harness(), load())
    assert report.recall_at_k >= MIN_RECALL_AT_5
    assert report.recall_passed


def test_metrics_are_bounded() -> None:
    report = evaluate_retrieval(build_harness(), load())
    assert 0.0 <= report.recall_at_k <= 1.0
    assert 0.0 <= report.precision_at_k <= 1.0


def test_recall_fails_for_unrecoverable_expectation() -> None:
    """A golden question demanding a non-existent chunk drives recall below 1.0."""

    impossible = [
        GoldenQuestion(
            id="impossible",
            question="O fabricante responde por defeitos do produto?",
            expected_chunk_ids=("does-not-exist",),
            expected_behavior="answered",
        )
    ]
    report = evaluate_retrieval(build_harness(), impossible)
    assert report.recall_at_k == 0.0
    assert not report.recall_passed
    assert "impossible" in report.failing_case_ids


def test_as_dict_carries_threshold() -> None:
    report = evaluate_retrieval(build_harness(), load())
    payload = report.as_dict()
    assert payload["retrieval_recall_at_5"]["threshold"] == MIN_RECALL_AT_5


def load() -> list[GoldenQuestion]:
    from packages.evals.golden import load_golden

    return load_golden()
