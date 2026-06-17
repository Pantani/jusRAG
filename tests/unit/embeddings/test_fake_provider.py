"""FakeEmbeddingProvider: determinism, normalization, semantic overlap (§27)."""

from __future__ import annotations

import math

from packages.embeddings.base import EmbeddingProvider
from packages.embeddings.fake_provider import FakeEmbeddingProvider


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return 0.0 if na == 0 or nb == 0 else dot / (na * nb)


def test_implements_protocol() -> None:
    assert isinstance(FakeEmbeddingProvider(), EmbeddingProvider)


def test_deterministic_same_text_same_vector() -> None:
    provider = FakeEmbeddingProvider()
    assert provider.embed_query("defeito do produto") == provider.embed_query("defeito do produto")


def test_vectors_are_l2_normalized() -> None:
    provider = FakeEmbeddingProvider()
    vec = provider.embed_query("fabricante responde por defeito")
    assert math.isclose(math.sqrt(sum(v * v for v in vec)), 1.0, rel_tol=1e-9)


def test_empty_text_yields_zero_vector_without_error() -> None:
    provider = FakeEmbeddingProvider(dim=16)
    vec = provider.embed_query("a o de")  # only stopwords
    assert vec == [0.0] * 16


def test_synonyms_collapse_to_shared_concept() -> None:
    provider = FakeEmbeddingProvider()
    # "desistência" maps to the same concept as "arrependimento".
    sim = _cosine(provider.embed_query("desistência"), provider.embed_query("arrependimento"))
    assert sim > 0.99


def test_lexical_overlap_drives_similarity() -> None:
    provider = FakeEmbeddingProvider()
    base = provider.embed_query("defeito do produto")
    near = provider.embed_query("produto com defeito de fabricação")
    far = provider.embed_query("prazo de arrependimento na compra")
    assert _cosine(base, near) > _cosine(base, far)


def test_embed_texts_batches() -> None:
    provider = FakeEmbeddingProvider()
    out = provider.embed_texts(["defeito", "arrependimento"])
    assert len(out) == 2
    assert out[0] != out[1]
