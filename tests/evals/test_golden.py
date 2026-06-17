"""Golden dataset integrity tests (§24): ≥30, unique ids, valid behaviors, in-corpus."""

from __future__ import annotations

import pytest

from packages.evals.golden import (
    in_scope_questions,
    load_golden,
    out_of_scope_questions,
)

# chunk_ids actually present in the seed corpus.
_SEED_CHUNK_IDS = {
    "cdc-8078-1990-art-6",
    "cdc-8078-1990-art-12",
    "cdc-8078-1990-art-14",
    "cdc-8078-1990-art-18",
    "cdc-8078-1990-art-26",
    "cdc-8078-1990-art-49",
    "stj-sumula-130",
    "stj-sumula-297",
    "stj-sumula-302",
    "stj-sumula-479",
    "stj-sumula-543",
}


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
