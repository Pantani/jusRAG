"""Golden dataset loader (§24, §35).

Reads every ``*_golden.yaml`` under ``data/seed/questions/`` into validated
``GoldenQuestion`` records. The dataset is the single source of truth shared by every
Phase-8 eval (retrieval, citation, answer). Pure I/O + validation — no network, no
embeddings.

Multi-area organisation (Phase E): the golden set is split one file per legal area
(``consumer_golden.yaml``, ``civil_golden.yaml``, ``criminal_golden.yaml``,
``labor_golden.yaml``, ``tax_golden.yaml``, ``constitutional_golden.yaml``). Each file
is loaded and concatenated; ids stay globally unique. An optional top-level ``area``
key on each item tags the question's legal area for per-area metrics; when absent it is
inferred from the file name (``<area>_golden.yaml``). Out-of-scope (refused) questions
keep their file's area for organisation but are reported under ``out_of_scope`` in the
refusal metric. The consumer file is loaded unchanged — its items carry no ``area`` key
and inherit ``consumer`` from the file name, so the existing golden set is untouched.

Each record's ``expected_chunk_ids`` are the seed chunks that retrieval must surface
(recall/precision@5); ``expected_behavior`` drives the refusal eval. The loader fails
loudly on a malformed file rather than silently dropping questions (system rule: no
silent fallbacks), so a broken golden set cannot quietly weaken the gate.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = _REPO_ROOT / "data" / "seed" / "questions"
GOLDEN_PATH = GOLDEN_DIR / "consumer_golden.yaml"
_GOLDEN_GLOB = "*_golden.yaml"

ExpectedBehavior = Literal["answered", "refused"]
_VALID_BEHAVIORS = ("answered", "refused")


@dataclass(frozen=True)
class GoldenQuestion:
    """One golden question with its expected retrieval and behavior."""

    id: str
    question: str
    expected_chunk_ids: tuple[str, ...]
    expected_behavior: ExpectedBehavior
    # ``load_golden`` always sets this (explicit ``area:`` key or inferred from the
    # file name). The default only serves ad-hoc construction in tests.
    area: str = "unknown"
    expected_articles: tuple[str, ...] = ()
    expected_sumulas: tuple[str, ...] = ()

    @property
    def in_scope(self) -> bool:
        """Answerable from the seed corpus (has expected sources / answered)."""

        return self.expected_behavior == "answered"

    @property
    def metric_area(self) -> str:
        """Area key for per-area metrics: refused questions group under out_of_scope."""

        return self.area if self.in_scope else "out_of_scope"


def _area_from_filename(path: Path) -> str:
    """Infer the legal area from ``<area>_golden.yaml`` (e.g. consumer, civil)."""

    name = path.stem
    return name[: -len("_golden")] if name.endswith("_golden") else name


def load_golden(path: Path | None = None) -> list[GoldenQuestion]:
    """Load and validate every golden question.

    With no argument, loads and concatenates **all** ``*_golden.yaml`` files under
    ``data/seed/questions/`` (sorted for determinism). A single ``path`` loads just
    that file (used by tests / single-area runs). Ids must be globally unique across
    every file.
    """

    if path is not None:
        return _load_one(path)
    files = sorted(GOLDEN_DIR.glob(_GOLDEN_GLOB))
    if not files:
        raise FileNotFoundError(
            f"no {_GOLDEN_GLOB} files in {GOLDEN_DIR} — the golden dataset is required for evals."
        )
    questions: list[GoldenQuestion] = []
    for f in files:
        questions.extend(_load_one(f))
    _check_unique_ids(questions)
    return questions


def _load_one(path: Path) -> list[GoldenQuestion]:
    """Load and validate one golden YAML file, tagging items with its area."""

    if not path.exists():
        raise FileNotFoundError(f"{path} not found — the golden dataset is required for evals.")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{path} must be a non-empty YAML list of questions.")
    default_area = _area_from_filename(path)
    questions = [_parse(item, idx, default_area) for idx, item in enumerate(raw)]
    _check_unique_ids(questions)
    return questions


def _parse(item: Any, idx: int, default_area: str) -> GoldenQuestion:
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
    raw_area = item.get("area")
    area = raw_area if isinstance(raw_area, str) and raw_area else default_area
    return GoldenQuestion(
        id=qid,
        question=question,
        expected_chunk_ids=tuple(item.get("expected_chunk_ids") or ()),
        expected_behavior=behavior,
        area=area,
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
    per_area: dict[str, int] = field(default_factory=dict)


def golden_stats(questions: list[GoldenQuestion]) -> GoldenStats:
    per_area: dict[str, int] = defaultdict(int)
    for q in questions:
        per_area[q.metric_area] += 1
    return GoldenStats(
        total=len(questions),
        in_scope=len(in_scope_questions(questions)),
        out_of_scope=len(out_of_scope_questions(questions)),
        ids=[q.id for q in questions],
        per_area=dict(sorted(per_area.items())),
    )
