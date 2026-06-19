"""Unit: AnswerWriter end-to-end with fake embedding/store/LLM (offline).

Builds the real retrieval pipeline over the shared CDC fixture chunks plus the
FakeLLMProvider, proving in-scope answering and out-of-scope safe refusal without
any network.
"""

from __future__ import annotations

import pytest

from packages.agents.classify_area import classify_area
from packages.answer.answer_writer import AnswerWriter, _is_out_of_scope
from packages.answer.schemas import AnswerStatus
from packages.embeddings.fake_provider import FakeEmbeddingProvider
from packages.legal_types.enums import LegalArea
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


# --- Scope gate (§2.2), CodeRabbit #3: UNKNOWN must not be pre-refused ----------------


def test_administrative_question_classifies_to_defined_out_of_scope_area() -> None:
    # (a) precondition: an administrative question is a *defined* out-of-scope area,
    # not UNKNOWN — so the pre-retrieval gate is allowed to refuse it.
    area = classify_area("Quero saber sobre improbidade administrativa de um prefeito")
    assert area is LegalArea.ADMINISTRATIVE
    assert _is_out_of_scope("Quero saber sobre improbidade administrativa de um prefeito")


def test_administrative_question_refuses_safely(writer: AnswerWriter) -> None:
    # (a) defined out-of-scope class (administrative) still pre-refuses before retrieval.
    answer = writer.write(
        "Quero saber sobre improbidade administrativa de um prefeito", top_k=3
    )
    assert answer.status is AnswerStatus.REFUSED
    assert answer.legal_basis == []
    assert answer.not_legal_advice is True


# --- Corpus-less regime signal (§2.2), agentic matched_out_of_scope_regime ------------
# These regimes classify UNKNOWN (no enum class) yet must pre-refuse deterministically:
# the explicit signal distinguishes them from no-evidence UNKNOWN. See
# _workspace/14_answer_oos_signal_consume_summary.md.


def test_inpi_trademark_regime_pre_refuses() -> None:
    # (a) INPI/marca: corpus-less regime matched -> UNKNOWN area but pre-refused.
    question = "Como registrar marca no INPI?"
    assert classify_area(question) is LegalArea.UNKNOWN
    assert _is_out_of_scope(question) is True


def test_inpi_trademark_regime_refuses_safely(writer: AnswerWriter) -> None:
    answer = writer.write("Como registrar marca no INPI?", top_k=3)
    assert answer.status is AnswerStatus.REFUSED
    assert answer.legal_basis == []
    assert answer.not_legal_advice is True


def test_environmental_licensing_regime_pre_refuses() -> None:
    # (b) licenciamento ambiental: corpus-less regime matched -> pre-refused.
    question = "Quais os requisitos do licenciamento ambiental?"
    assert classify_area(question) is LegalArea.UNKNOWN
    assert _is_out_of_scope(question) is True


def test_environmental_licensing_regime_refuses_safely(writer: AnswerWriter) -> None:
    answer = writer.write("Quais os requisitos do licenciamento ambiental?", top_k=3)
    assert answer.status is AnswerStatus.REFUSED
    assert answer.legal_basis == []


def test_social_security_regime_pre_refuses() -> None:
    question = "Aposentadoria por tempo de contribuicao no INSS"
    assert classify_area(question) is LegalArea.UNKNOWN
    assert _is_out_of_scope(question) is True


def test_unknown_no_evidence_question_is_not_pre_refused_by_scope_gate() -> None:
    # (b) an in-corpus question (judicial inventory: CC art. 610 / CPC) the keyword map
    # fails to recognize classifies UNKNOWN. UNKNOWN must NOT be pre-refused: grounding is
    # left to retrieval/auditor, mirroring the researcher-node contract (§14/§15.2).
    question = "Como funciona o procedimento de arrolamento dos bens deixados?"
    assert classify_area(question) is LegalArea.UNKNOWN
    assert _is_out_of_scope(question) is False


def test_in_scope_civil_usucapiao_is_not_pre_refused() -> None:
    # (c/e) usucapião classifies CIVIL (in scope) -> not pre-refused.
    question = "Quais os requisitos da usucapião extraordinária de imóvel?"
    assert classify_area(question) is LegalArea.CIVIL
    assert _is_out_of_scope(question) is False


def test_unknown_question_can_be_answered_when_retrieval_grounds_it(
    cdc_chunks: list[LegalChunk],
) -> None:
    # (b) end-to-end: a question classified UNKNOWN reaches retrieval and, when a real
    # source surfaces, is answered — not refused by the scope gate. The fake embedding
    # matches lexical overlap, so we phrase the (UNKNOWN-classified) question around the
    # in-corpus art. 12 text to force a grounded hit.
    question = "O fabricante e o importador respondem pela reparacao dos danos?"
    assert classify_area(question) is LegalArea.UNKNOWN  # no keyword evidence

    embeddings = FakeEmbeddingProvider()
    store = InMemoryVectorStore()
    store.upsert_chunks(cdc_chunks, embeddings.embed_texts([c.text for c in cdc_chunks]))
    service = SearchService(LegalRetriever(embeddings, store))
    writer = AnswerWriter(service, FakeLLMProvider())

    answer = writer.write(question, top_k=3)
    assert answer.status is AnswerStatus.ANSWERED
    assert answer.sources, "a grounded UNKNOWN question must carry sources"
