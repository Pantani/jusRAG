"""InMemoryVectorStore: cosine ranking, idempotent upsert, metadata filters (§28)."""

from __future__ import annotations

from packages.embeddings.fake_provider import FakeEmbeddingProvider
from packages.legal_types.schemas import LegalChunk
from packages.storage.base import VectorSearchResult, VectorStore
from packages.storage.memory import InMemoryVectorStore


def _index(chunks: list[LegalChunk]) -> tuple[InMemoryVectorStore, FakeEmbeddingProvider]:
    provider = FakeEmbeddingProvider()
    store = InMemoryVectorStore()
    store.upsert_chunks(chunks, provider.embed_texts([c.text for c in chunks]))
    return store, provider


def test_implements_protocol() -> None:
    assert isinstance(InMemoryVectorStore(), VectorStore)


def test_upsert_is_idempotent(cdc_chunks: list[LegalChunk]) -> None:
    store, provider = _index(cdc_chunks)
    store.upsert_chunks(cdc_chunks, provider.embed_texts([c.text for c in cdc_chunks]))
    assert len(store) == len(cdc_chunks)


def test_search_returns_results_with_score_and_metadata(
    cdc_chunks: list[LegalChunk],
) -> None:
    store, provider = _index(cdc_chunks)
    results = store.search(provider.embed_query("defeito do produto"), top_k=3)
    assert results
    assert all(isinstance(r, VectorSearchResult) for r in results)
    top = results[0]
    assert top.payload["article"] == "12"
    assert top.metadata == {"is_current": True}
    assert 0.0 <= top.score <= 1.0


def test_results_sorted_descending_by_score(cdc_chunks: list[LegalChunk]) -> None:
    store, provider = _index(cdc_chunks)
    results = store.search(provider.embed_query("arrependimento desistência"), top_k=4)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_metadata_filter_restricts_results(cdc_chunks: list[LegalChunk]) -> None:
    store, provider = _index(cdc_chunks)
    results = store.search(provider.embed_query("defeito"), top_k=10, filters={"article": "12"})
    assert {r.payload["article"] for r in results} == {"12"}
