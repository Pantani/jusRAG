"""Unit: AnswerWriter end-to-end with fake embedding/store/LLM (offline).

Builds the real retrieval pipeline over the shared CDC fixture chunks plus the
FakeLLMProvider, proving in-scope answering and out-of-scope safe refusal without
any network.
"""

from __future__ import annotations

import pytest

from packages.answer.answer_writer import AnswerWriter
from packages.answer.schemas import AnswerStatus
from packages.embeddings.fake_provider import FakeEmbeddingProvider
from packages.legal_types.schemas import LegalChunk
from packages.llm.fake_provider import FakeLLMProvider
from packages.rag.retriever import LegalRetriever
from packages.rag.search_service import SearchService
from packages.storage.memory import InMemoryVectorStore


@pytest.fixture
def writer(cdc_chunks: list[LegalChunk]) -> AnswerWriter:
    embeddings = FakeEmbeddingProvider()
    store = InMemoryVectorStore()
    store.upsert_chunks(cdc_chunks, embeddings.embed_texts([c.text for c in cdc_chunks]))
    service = SearchService(LegalRetriever(embeddings, store))
    return AnswerWriter(service, FakeLLMProvider())


@pytest.fixture
def writer_with_case_law(
    cdc_chunks: list[LegalChunk],
    case_law_chunks: list[LegalChunk],
) -> AnswerWriter:
    embeddings = FakeEmbeddingProvider()
    store = InMemoryVectorStore()
    chunks = cdc_chunks + case_law_chunks
    store.upsert_chunks(chunks, embeddings.embed_texts([c.text for c in chunks]))
    service = SearchService(LegalRetriever(embeddings, store))
    return AnswerWriter(service, FakeLLMProvider())


def test_consumer_question_returns_separated_case_law_block(
    writer_with_case_law: AnswerWriter,
) -> None:
    answer = writer_with_case_law.write(
        "O CDC se aplica a banco e instituição financeira?", top_k=5
    )

    assert answer.status is AnswerStatus.ANSWERED
    # (a) Jurisprudence appears in its own block, with a real source, led by Súmula 297.
    chunk_ids = {c.chunk_id for c in answer.case_law}
    assert "stj-sumula-297" in chunk_ids
    sumula = next(c for c in answer.case_law if c.chunk_id == "stj-sumula-297")
    assert sumula.court == "STJ"
    assert sumula.source_url
    # legal_basis (legislation) never carries a case_law chunk id — blocks are separated.
    cited = {c for b in answer.legal_basis for c in b.citations}
    assert not any(cid.startswith("stj-sumula") for cid in cited)


def test_question_without_relevant_case_law_has_no_block(writer: AnswerWriter) -> None:
    # (b) No jurisprudence indexed -> no case_law block, nothing invented.
    answer = writer.write("O fornecedor responde por defeito do produto?", top_k=3)
    assert answer.status is AnswerStatus.ANSWERED
    assert answer.case_law == []


def test_in_scope_question_cites_art_12(writer: AnswerWriter) -> None:
    answer = writer.write("O fornecedor responde por defeito do produto?", top_k=3)

    assert answer.status is AnswerStatus.ANSWERED
    assert answer.not_legal_advice is True
    assert answer.sources, "every answer must carry sources"
    cited = {c for b in answer.legal_basis for c in b.citations}
    assert "cdc-8078-1990-art-12" in cited
    # No citation may point outside the recovered sources.
    source_ids = {s.chunk_id for s in answer.sources}
    assert cited <= source_ids


def test_out_of_scope_question_refuses_safely(writer: AnswerWriter) -> None:
    answer = writer.write("Qual a alíquota do imposto de renda sobre criptomoedas?", top_k=3)

    assert answer.status is AnswerStatus.REFUSED
    assert answer.legal_basis == []
    assert answer.not_legal_advice is True


def test_no_chunks_at_all_refuses(cdc_chunks: list[LegalChunk]) -> None:
    embeddings = FakeEmbeddingProvider()
    store = InMemoryVectorStore()  # empty store
    service = SearchService(LegalRetriever(embeddings, store))
    writer = AnswerWriter(service, FakeLLMProvider())

    answer = writer.write("O fornecedor responde por defeito do produto?", top_k=3)
    assert answer.status is AnswerStatus.REFUSED
