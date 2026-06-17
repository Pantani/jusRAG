"""LegalRetriever acceptance: defeito -> art. 12, arrependimento -> art. 49 (§19)."""

from __future__ import annotations

import pytest

from packages.embeddings.fake_provider import FakeEmbeddingProvider
from packages.legal_types.schemas import LegalChunk
from packages.rag.query_analyzer import extract_article
from packages.rag.retriever import LegalRetriever
from packages.rag.types import RetrievalQuery
from packages.storage.memory import InMemoryVectorStore


@pytest.fixture
def retriever(cdc_chunks: list[LegalChunk]) -> LegalRetriever:
    provider = FakeEmbeddingProvider()
    store = InMemoryVectorStore()
    store.upsert_chunks(cdc_chunks, provider.embed_texts([c.text for c in cdc_chunks]))
    return LegalRetriever(provider, store)


def test_defeito_do_produto_returns_art_12(retriever: LegalRetriever) -> None:
    hits = retriever.retrieve(RetrievalQuery(query="defeito do produto", top_k=3))
    assert hits[0].citation.article == "12"


def test_arrependimento_returns_art_49(retriever: LegalRetriever) -> None:
    hits = retriever.retrieve(
        RetrievalQuery(query="direito de arrependimento e desistência", top_k=3)
    )
    assert hits[0].citation.article == "49"


def test_hit_carries_score_and_citation_metadata(retriever: LegalRetriever) -> None:
    top = retriever.retrieve(RetrievalQuery(query="defeito do produto", top_k=1))[0]
    assert top.score > 0
    assert top.citation.chunk_id == "cdc-8078-1990-art-12"
    assert top.citation.source_url
    assert top.citation.doc_type == "statute"


def test_empty_query_returns_nothing(retriever: LegalRetriever) -> None:
    assert retriever.retrieve(RetrievalQuery(query="   ", top_k=5)) == []


def test_doc_type_filter_passed_through(retriever: LegalRetriever) -> None:
    hits = retriever.retrieve(
        RetrievalQuery(query="defeito do produto", top_k=5, doc_type="case_law")
    )
    assert hits == []  # seed has only statutes


def test_extract_article_helper() -> None:
    assert extract_article("o que diz o art. 49 do CDC?") == "49"
    assert extract_article("artigo 12") == "12"
    assert extract_article("defeito do produto") is None
