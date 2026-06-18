"""Golden dataset integrity tests (§24): ≥30, unique ids, valid behaviors, in-corpus."""

from __future__ import annotations

import pytest

from apps.worker.jobs.chunk_jsonl import load_indexable_chunks
from packages.evals.golden import (
    golden_stats,
    in_scope_questions,
    load_golden,
    out_of_scope_questions,
)

# Areas the multi-area golden must cover in-scope (Phase E user decision).
_REQUIRED_AREAS = {"consumer", "civil", "criminal", "labor", "tax", "constitutional"}

# chunk_ids actually present in the seed corpus (CDC + STJ jurisprudence).
# Derived from the indexed corpus so the test scales with §22 corpus expansions
# instead of drifting out of sync with a hand-maintained allowlist.
_SEED_CHUNK_IDS = {c.chunk_id for c in load_indexable_chunks()}


def test_golden_has_at_least_30_questions() -> None:
    assert len(load_golden()) >= 30


def test_golden_ids_are_unique() -> None:
    questions = load_golden()
    ids = [q.id for q in questions]
    assert len(ids) == len(set(ids))


def test_golden_includes_out_of_scope_for_refusal() -> None:
    oos = out_of_scope_questions(load_golden())
    assert len(oos) >= 5
    for q in oos:
        assert q.expected_chunk_ids == ()


def test_expected_chunk_ids_are_in_corpus() -> None:
    """No invented sources: every expected chunk must exist in the seed (§2.1)."""

    for q in in_scope_questions(load_golden()):
        assert q.expected_chunk_ids, f"{q.id} in-scope but has no expected chunk"
        for cid in q.expected_chunk_ids:
            assert cid in _SEED_CHUNK_IDS, f"{q.id} references unknown chunk {cid}"


def test_behaviors_are_valid() -> None:
    for q in load_golden():
        assert q.expected_behavior in ("answered", "refused")


def test_load_golden_rejects_missing_file() -> None:
    from pathlib import Path

    with pytest.raises(FileNotFoundError):
        load_golden(Path("/nonexistent/golden.yaml"))


def test_every_question_has_an_area() -> None:
    """Phase E: each question carries a legal area (explicit or file-inferred)."""

    for q in load_golden():
        assert q.area, f"{q.id} has no area"


def test_multiarea_in_scope_coverage() -> None:
    """Each new area carries >= 10 in-scope golden questions (Phase E gate)."""

    per_area = golden_stats(in_scope_questions(load_golden())).per_area
    for area in _REQUIRED_AREAS:
        assert per_area.get(area, 0) >= 10, f"area {area} has < 10 in-scope questions"


def test_refused_questions_group_under_out_of_scope() -> None:
    """A refused question reports under the out_of_scope metric area regardless of file."""

    for q in out_of_scope_questions(load_golden()):
        assert q.metric_area == "out_of_scope"


def test_single_file_load_infers_area_from_name() -> None:
    from packages.evals.golden import GOLDEN_DIR

    civil = load_golden(GOLDEN_DIR / "civil_golden.yaml")
    assert civil and all(q.area == "civil" for q in civil)
