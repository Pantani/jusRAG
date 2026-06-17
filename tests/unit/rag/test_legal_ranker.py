"""Composite legal ranking (§38) and authority lookup (§39)."""

from __future__ import annotations

import math

from packages.rag.legal_ranker import (
    AUTHORITY_WEIGHT,
    CITATION_WEIGHT,
    SEMANTIC_WEIGHT,
    authority_for_payload,
    composite_score,
    exact_citation_match,
)
from packages.storage.base import VectorSearchResult


def _hit(
    score: float, *, doc_type: str = "statute", norm_type: str = "lei", article: str = "12"
) -> VectorSearchResult:
    payload = {
        "chunk_id": "c",
        "doc_type": doc_type,
        "norm_type": norm_type,
        "article": article,
        "source": "planalto",
        "text": "x",
        "title": "t",
    }
    return VectorSearchResult(chunk_id="c", score=score, text="x", payload=payload)


def test_weights_sum_to_one() -> None:
    assert math.isclose(SEMANTIC_WEIGHT + AUTHORITY_WEIGHT + CITATION_WEIGHT, 1.0, rel_tol=1e-9)


def test_federal_law_statute_authority() -> None:
    assert authority_for_payload(_hit(0.5).payload) == 0.95


def test_unknown_doc_type_authority_floor() -> None:
    assert authority_for_payload({"doc_type": "weird"}) == 0.10


def test_exact_citation_match() -> None:
    assert exact_citation_match({"article": "12"}, "12") == 1.0
    assert exact_citation_match({"article": "12"}, "49") == 0.0
    assert exact_citation_match({"article": "12"}, None) == 0.0


def test_composite_score_formula() -> None:
    score, semantic = composite_score(_hit(0.8, article="12"), requested_article="12")
    expected = 0.70 * 0.8 + 0.20 * 0.95 + 0.10 * 1.0
    assert abs(score - expected) < 1e-9
    assert semantic == 0.8


def test_semantic_score_clamped() -> None:
    _, semantic = composite_score(_hit(1.5), requested_article=None)
    assert semantic == 1.0
