"""HybridRetriever tests — opt-in semantic+BM25 fusion (§4, §38)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.config.settings import Settings
from packages.embeddings.fake_provider import FakeEmbeddingProvider
from packages.legal_types.enums import DocType, LegalArea, Source
from packages.legal_types.schemas import LegalChunk
from packages.rag.hybrid_retriever import HybridRetriever
from packages.rag.retriever import LegalRetriever
from packages.rag.types import RetrievalQuery
from packages.storage.memory import InMemoryVectorStore
from packages.storage.opensearch import FakeBM25Store


def _settings(**overrides: object) -> Settings:
    # Required infra envs that have no defaults in Settings.
    base: dict[str, object] = {
        "postgres_host": "localhost",
        "postgres_port": 5432,
        "postgres_db": "jus_rag",
        "postgres_user": "jus",
        "postgres_password": "jus",
        "qdrant_url": "http://localhost:6333",
        "redis_url": "redis://localhost:6379/0",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.fixture
def stack(cdc_chunks: list[LegalChunk]) -> tuple[
    FakeEmbeddingProvider, InMemoryVectorStore, FakeBM25Store, list[LegalChunk]
]:
    provider = FakeEmbeddingProvider()
    store = InMemoryVectorStore()
    store.upsert_chunks(cdc_chunks, provider.embed_texts([c.text for c in cdc_chunks]))
    bm25 = FakeBM25Store()
    bm25.index_chunks(cdc_chunks)
    return provider, store, bm25, cdc_chunks


def test_hybrid_disabled_matches_semantic_baseline(
    stack: tuple[FakeEmbeddingProvider, InMemoryVectorStore, FakeBM25Store, list[LegalChunk]],
) -> None:
    provider, store, bm25, _ = stack
    baseline = LegalRetriever(provider, store)
    hybrid = HybridRetriever(provider, store, _settings(enable_hybrid=False), bm25=bm25)

    for q in ["defeito do produto", "direito de arrependimento", "vício de qualidade"]:
        req = RetrievalQuery(query=q, top_k=4)
        a = [(c.chunk_id, round(c.score, 6)) for c in baseline.retrieve(req)]
        b = [(c.chunk_id, round(c.score, 6)) for c in hybrid.retrieve(req)]
        assert a == b, f"hybrid OFF must equal semantic baseline for {q!r}"


def test_phase3_acceptance_still_green_with_hybrid_off(
    stack: tuple[FakeEmbeddingProvider, InMemoryVectorStore, FakeBM25Store, list[LegalChunk]],
) -> None:
    provider, store, bm25, _ = stack
    hybrid = HybridRetriever(provider, store, _settings(enable_hybrid=False), bm25=bm25)
    assert hybrid.retrieve(RetrievalQuery(query="defeito do produto", top_k=3))[
        0
    ].citation.article == "12"
    assert hybrid.retrieve(
        RetrievalQuery(query="direito de arrependimento e desistência", top_k=3)
    )[0].citation.article == "49"


def _art14_chunk() -> LegalChunk:
    return LegalChunk(
        chunk_id="cdc-8078-1990-art-14",
        document_id="cdc-8078-1990",
        doc_type=DocType.STATUTE,
        source=Source.PLANALTO,
        title="Código de Defesa do Consumidor (Lei nº 8.078/1990)",
        legal_area=LegalArea.CONSUMER,
        jurisdiction="federal",
        norm_type="lei",
        norm_number="8078",
        norm_year="1990",
        article="14",
        text=(
            "## Art. 14\n\nO fornecedor de serviços responde, independentemente de "
            "culpa, pela reparação dos danos causados aos consumidores por defeitos "
            "relativos à prestação dos serviços."
        ),
        source_url="https://www.planalto.gov.br/ccivil_03/leis/l8078.htm",
        version="2026-06-16",
        content_hash="sha256:fixture-14",
        created_at=datetime(2026, 6, 16, tzinfo=UTC),
        metadata={"is_current": True},
    )


def test_hybrid_enabled_boosts_exact_article_match(
    cdc_chunks: list[LegalChunk],
) -> None:
    # Seed includes arts. 12, 18, 26, 49; add art. 14 explicitly so the BM25
    # lexical signal can disambiguate the "art. 14" query.
    chunks = [*cdc_chunks, _art14_chunk()]
    provider = FakeEmbeddingProvider()
    store = InMemoryVectorStore()
    store.upsert_chunks(chunks, provider.embed_texts([c.text for c in chunks]))
    bm25 = FakeBM25Store()
    bm25.index_chunks(chunks)

    query = RetrievalQuery(query="art. 14 CDC defeito serviço", top_k=4)

    semantic_only = LegalRetriever(provider, store).retrieve(query)
    hybrid_on = HybridRetriever(
        provider, store, _settings(enable_hybrid=True), bm25=bm25
    ).retrieve(query)

    assert hybrid_on[0].citation.article == "14"
    # The exact_citation_match term (0.10) already boosts art. 14 in semantic-
    # only ranking; the hybrid run must NOT lose that ordering and additionally
    # widens the gap over art. 12 thanks to BM25 token overlap on "serviço".
    sem_ids = [c.citation.article for c in semantic_only]
    hyb_ids = [c.citation.article for c in hybrid_on]
    assert hyb_ids.index("14") <= sem_ids.index("14")


def test_hybrid_weights_validation() -> None:
    with pytest.raises(ValidationError):
        _settings(enable_hybrid=True, hybrid_semantic_weight=0.5, hybrid_bm25_weight=0.3)
    with pytest.raises(ValidationError):
        _settings(hybrid_semantic_weight=0.8, hybrid_bm25_weight=0.3)
    # Valid combo does not raise.
    _settings(hybrid_semantic_weight=0.6, hybrid_bm25_weight=0.4)


def test_hybrid_fake_opensearch_deterministic(
    stack: tuple[FakeEmbeddingProvider, InMemoryVectorStore, FakeBM25Store, list[LegalChunk]],
) -> None:
    provider, store, bm25, _ = stack
    retriever = HybridRetriever(provider, store, _settings(enable_hybrid=True), bm25=bm25)
    req = RetrievalQuery(query="defeito do produto fabricante", top_k=4)
    a = [(c.chunk_id, round(c.score, 8)) for c in retriever.retrieve(req)]
    b = [(c.chunk_id, round(c.score, 8)) for c in retriever.retrieve(req)]
    assert a == b
