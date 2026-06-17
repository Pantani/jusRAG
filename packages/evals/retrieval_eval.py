"""Retrieval evaluation — recall@k and precision@k over the golden set (§24, §36).

Runs the *real* retriever (``SearchService``) on the deterministic harness for every
in-scope golden question and compares the top-k ``chunk_id`` list against the
question's ``expected_chunk_ids``.

* ``recall@k``  — micro-averaged: total expected chunks found in top-k over total
  expected chunks. The §36 gate is ``recall@5 ≥ 0.80``.
* ``precision@k`` — micro-averaged: total relevant retrieved over total retrieved
  (capped at k per question). Reported for transparency; not a gate.

Out-of-scope questions have no expected chunks and are excluded from retrieval
metrics (they are scored by the answer/refusal eval instead). Pure and offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.evals.golden import GoldenQuestion, in_scope_questions
from packages.evals.harness import EvalHarness
from packages.rag.search_service import SearchService

# v1 quality gate threshold (§36).
MIN_RECALL_AT_5 = 0.80
DEFAULT_K = 5


@dataclass(frozen=True)
class RetrievalCase:
    """Per-question retrieval outcome for report drill-down."""

    case_id: str
    expected: list[str]
    retrieved: list[str]
    hits: int
    recall: float
    precision: float


@dataclass(frozen=True)
class RetrievalEvalReport:
    """Corpus retrieval metrics with the recall@k gate verdict (§36)."""

    k: int
    recall_at_k: float
    precision_at_k: float
    total_expected: int
    total_found: int
    cases: list[RetrievalCase] = field(default_factory=list)
    recall_passed: bool = True
    failing_case_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            f"retrieval_recall_at_{self.k}": {
                "value": self.recall_at_k,
                "threshold": MIN_RECALL_AT_5,
                "passed": self.recall_passed,
            },
            f"retrieval_precision_at_{self.k}": {"value": self.precision_at_k},
            "total_expected": self.total_expected,
            "total_found": self.total_found,
            "failing_case_ids": list(self.failing_case_ids),
            "cases": [
                {
                    "case_id": c.case_id,
                    "expected": c.expected,
                    "retrieved": c.retrieved,
                    "hits": c.hits,
                    "recall": c.recall,
                    "precision": c.precision,
                }
                for c in self.cases
            ],
        }


def _eval_one(search: SearchService, q: GoldenQuestion, k: int) -> RetrievalCase:
    retrieved = [r.chunk_id for r in search.search(q.question, top_k=k)]
    expected = set(q.expected_chunk_ids)
    hits = sum(1 for cid in retrieved if cid in expected)
    recall = hits / len(expected) if expected else 1.0
    precision = hits / len(retrieved) if retrieved else 0.0
    return RetrievalCase(
        case_id=q.id,
        expected=list(q.expected_chunk_ids),
        retrieved=retrieved,
        hits=hits,
        recall=recall,
        precision=precision,
    )


def evaluate_retrieval(
    harness: EvalHarness,
    questions: list[GoldenQuestion],
    *,
    k: int = DEFAULT_K,
    min_recall: float = MIN_RECALL_AT_5,
) -> RetrievalEvalReport:
    """Micro-averaged recall@k / precision@k over in-scope golden questions."""

    in_scope = in_scope_questions(questions)
    cases = [_eval_one(harness.search, q, k) for q in in_scope]

    total_expected = sum(len(c.expected) for c in cases)
    total_found = sum(c.hits for c in cases)
    total_retrieved = sum(len(c.retrieved) for c in cases)

    recall = total_found / total_expected if total_expected else 1.0
    precision = total_found / total_retrieved if total_retrieved else 0.0
    recall_passed = recall >= min_recall
    failing = [c.case_id for c in cases if c.hits < len(c.expected)]

    return RetrievalEvalReport(
        k=k,
        recall_at_k=recall,
        precision_at_k=precision,
        total_expected=total_expected,
        total_found=total_found,
        cases=cases,
        recall_passed=recall_passed,
        failing_case_ids=failing,
    )
