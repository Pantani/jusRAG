"""Golden dataset loader (§24, §35).

Reads ``data/seed/questions/consumer_golden.yaml`` into validated ``GoldenQuestion``
records. The dataset is the single source of truth shared by every Phase-8 eval
(retrieval, citation, answer). Pure I/O + validation — no network, no embeddings.

Each record's ``expected_chunk_ids`` are the seed chunks that retrieval must surface
(recall/precision@5); ``expected_behavior`` drives the refusal eval. The loader fails
loudly on a malformed file rather than silently dropping questions (system rule: no
silent fallbacks), so a broken golden set cannot quietly weaken the gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = _REPO_ROOT / "data" / "seed" / "questions" / "consumer_golden.yaml"

ExpectedBehavior = Literal["answered", "refused"]
_VALID_BEHAVIORS = ("answered", "refused")


@dataclass(frozen=True)
class GoldenQuestion:
    """One golden question with its expected retrieval and behavior."""

    id: str
    question: str
    expected_chunk_ids: tuple[str, ...]
    expected_behavior: ExpectedBehavior
    expected_articles: tuple[str, ...] = ()
    expected_sumulas: tuple[str, ...] = ()

    @property
    def in_scope(self) -> bool:
        """Answerable from the seed corpus (has expected sources / answered)."""

        return self.expected_behavior == "answered"


def load_golden(path: Path = GOLDEN_PATH) -> list[GoldenQuestion]:
    """Load and validate every golden question from the YAML."""

    if not path.exists():
        raise FileNotFoundError(f"{path} not found — the golden dataset is required for evals.")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{path} must be a non-empty YAML list of questions.")
    questions = [_parse(item, idx) for idx, item in enumerate(raw)]
    _check_unique_ids(questions)
    return questions


def _parse(item: Any, idx: int) -> GoldenQuestion:
    if not isinstance(item, dict):
        raise ValueError(f"golden item #{idx} is not a mapping: {item!r}")
    behavior = item.get("expected_behavior")
    if behavior not in _VALID_BEHAVIORS:
        raise ValueError(
            f"golden item #{idx} ({item.get('id')!r}) has invalid "
            f"expected_behavior={behavior!r}; must be one of {_VALID_BEHAVIORS}"
        )
    qid = item.get("id")
    question = item.get("question")
    if not isinstance(qid, str) or not qid:
        raise ValueError(f"golden item #{idx} is missing a non-empty 'id'.")
    if not isinstance(question, str) or not question:
        raise ValueError(f"golden item {qid!r} is missing a non-empty 'question'.")
    return GoldenQuestion(
        id=qid,
        question=question,
        expected_chunk_ids=tuple(item.get("expected_chunk_ids") or ()),
        expected_behavior=behavior,
        expected_articles=tuple(str(a) for a in (item.get("expected_articles") or ())),
        expected_sumulas=tuple(str(s) for s in (item.get("expected_sumulas") or ())),
    )


def _check_unique_ids(questions: list[GoldenQuestion]) -> None:
    seen: set[str] = set()
    dupes: list[str] = []
    for q in questions:
        if q.id in seen:
            dupes.append(q.id)
        seen.add(q.id)
    if dupes:
        raise ValueError(f"duplicate golden ids: {sorted(set(dupes))}")


def in_scope_questions(questions: list[GoldenQuestion]) -> list[GoldenQuestion]:
    """Questions answerable from the seed corpus (for retrieval recall/precision)."""

    return [q for q in questions if q.in_scope]


def out_of_scope_questions(questions: list[GoldenQuestion]) -> list[GoldenQuestion]:
    """Questions that must be safely refused (for refusal rate)."""

    return [q for q in questions if not q.in_scope]


@dataclass(frozen=True)
class GoldenStats:
    """Headcount of the loaded golden set for the report."""

    total: int
    in_scope: int
    out_of_scope: int
    ids: list[str] = field(default_factory=list)


def golden_stats(questions: list[GoldenQuestion]) -> GoldenStats:
    return GoldenStats(
        total=len(questions),
        in_scope=len(in_scope_questions(questions)),
        out_of_scope=len(out_of_scope_questions(questions)),
        ids=[q.id for q in questions],
    )
