"""Fase 6 retrieval: statute vs case_law separation (§4/§22).

Proves, fully offline (fake provider + in-memory store), that:
(a) doc_type=case_law surfaces the STJ súmula and never a statute;
(b) doc_type=statute surfaces CDC articles and never a súmula;
(c) a consumer query with no filter returns both, each carrying its doc_type;
(d) case_law only appears when a source was indexed (never fabricated, §22);
and that a STJ súmula scores at the 0.88 authority tier, not the 0.75 fallback.
"""

from __future__ import annotations

import pytest

from packages.embeddings.fake_provider import FakeEmbeddingProvider
from packages.legal_types.hierarchy import AuthorityTier, weight_for
from packages.legal_types.schemas import LegalChunk
from packages.rag.legal_ranker import authority_for_payload
from packages.rag.retriever import LegalRetriever
from packages.rag.types import RetrievalQuery
from packages.storage.memory import InMemoryVectorStore

_BANK_QUERY = "CDC aplica-se a banco e instituição financeira"


def _build(chunks: list[LegalChunk]) -> LegalRetriever:
    provider = FakeEmbeddingProvider()
    store = InMemoryVectorStore()
    store.upsert_chunks(chunks, provider.embed_texts([c.text for c in chunks]))
    return LegalRetriever(provider, store)


@pytest.fixture
def mixed_retriever(
    cdc_chunks: list[LegalChunk], case_law_chunks: list[LegalChunk]
) -> LegalRetriever:
    return _build(cdc_chunks + case_law_chunks)


def test_case_law_filter_returns_only_sumulas(mixed_retriever: LegalRetriever) -> None:
    hits = mixed_retriever.retrieve(
        RetrievalQuery(query=_BANK_QUERY, top_k=5, doc_type="case_law")
    )
    assert hits, "expected the STJ súmula to be retrievable for a banking query"
    assert all(h.citation.doc_type == "case_law" for h in hits)
    assert hits[0].chunk_id == "stj-sumula-297"


def test_statute_filter_returns_only_articles(mixed_retriever: LegalRetriever) -> None:
    hits = mixed_retriever.retrieve(
        RetrievalQuery(query="defeito do produto", top_k=5, doc_type="statute")
    )
    assert hits
    assert all(h.citation.doc_type == "statute" for h in hits)
    assert all(not h.chunk_id.startswith("stj-sumula") for h in hits)
    assert hits[0].citation.article == "12"


def test_unfiltered_query_returns_both_blocks(mixed_retriever: LegalRetriever) -> None:
    blocks = mixed_retriever.retrieve_separated(RetrievalQuery(query=_BANK_QUERY, top_k=5))
    assert blocks.statutes, "consumer query should still surface statutes"
    assert blocks.case_law, "consumer banking query should surface the STJ súmula"
    assert all(h.citation.doc_type == "statute" for h in blocks.statutes)
    assert all(h.citation.doc_type == "case_law" for h in blocks.case_law)
    assert "stj-sumula-297" in {h.chunk_id for h in blocks.case_law}


def test_case_law_block_empty_without_source(cdc_chunks: list[LegalChunk]) -> None:
    # No jurisprudence indexed -> case_law block stays empty; nothing fabricated.
    retriever = _build(cdc_chunks)
    blocks = retriever.retrieve_separated(RetrievalQuery(query=_BANK_QUERY, top_k=5))
    assert blocks.case_law == []
    assert blocks.statutes


def test_stj_sumula_authority_is_088(case_law_chunks: list[LegalChunk]) -> None:
    from packages.storage.payload import chunk_to_payload

    payload = chunk_to_payload(case_law_chunks[0])
    assert authority_for_payload(payload) == pytest.approx(
        weight_for(AuthorityTier.STJ_SUMMARY)
    )
    assert authority_for_payload(payload) == pytest.approx(0.88)
