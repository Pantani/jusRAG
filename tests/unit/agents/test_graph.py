"""Unit: LangGraph runtime (§13–§15) end-to-end and per-node, fully offline.

Drives the compiled §14 graph with the fake embedder/store/LLM over the shared CDC +
case-law fixtures. Proves the three §14 routing scenarios:
  (answered) in-scope consumer question → status=answered with final_answer, sources,
             audit and caveats;
  (refused)  out-of-scope question → status=refused, nothing invented;
  (retry)    a hallucinating LLM fails the audit → synthesis re-runs once, then the
             answer is conservatively recovered or safely refused.
Plus a needs_more_info route and standalone node tests.
"""

from __future__ import annotations

from packages.agents.answer_writer import AnswerBuffer, make_answer_writer
from packages.agents.classify_area import classify_area, run_classify_area
from packages.agents.graph import build_graph, run_graph
from packages.agents.intake import run_intake
from packages.agents.state import LegalResearchState
from packages.agents.trace import RETRY_MARKER, TraceCollector, retry_attempts
from packages.embeddings.fake_provider import FakeEmbeddingProvider
from packages.legal_types.enums import LegalArea
from packages.legal_types.schemas import LegalChunk
from packages.llm.base import DraftLegalBasis, LLMAnswerDraft, LLMMessage
from packages.llm.fake_provider import FakeLLMProvider
from packages.rag.context_builder import BuiltContext
from packages.rag.retriever import LegalRetriever
from packages.rag.search_service import SearchService
from packages.storage.memory import InMemoryVectorStore


def _service(chunks: list[LegalChunk]) -> SearchService:
    embeddings = FakeEmbeddingProvider()
    store = InMemoryVectorStore()
    store.upsert_chunks(chunks, embeddings.embed_texts([c.text for c in chunks]))
    return SearchService(LegalRetriever(embeddings, store))


class _HallucinatingLLM:
    """Asserts an article absent from the recovered context (forces audit failure)."""

    def generate_answer(
        self, messages: list[LLMMessage], context: BuiltContext
    ) -> LLMAnswerDraft:
        grounded = next(c for c in context.chunks if c.citation.article == "12")
        return LLMAnswerDraft(
            short_answer="O fornecedor responde por defeito do produto.",
            legal_basis=[
                DraftLegalBasis(
                    text=(
                        "Segundo o art. 12, o fabricante responde, independentemente "
                        "de culpa, pelos defeitos do produto."
                    ),
                    citations=[grounded.chunk_id],
                ),
                DraftLegalBasis(
                    text=(
                        "Conforme o art. 999 do CDC, há indenização automática e "
                        "garantida em qualquer caso."
                    ),
                    citations=[grounded.chunk_id],
                ),
            ],
            caveats=[],
        )


# --- scenario 1: answered -----------------------------------------------------


def test_in_scope_question_is_answered_with_full_state(
    cdc_chunks: list[LegalChunk],
    case_law_chunks: list[LegalChunk],
) -> None:
    service = _service(cdc_chunks + case_law_chunks)
    collector = TraceCollector()
    state = run_graph(
        "O fornecedor responde por defeito do produto?",
        run_id="run-answered",
        search=service,
        llm=FakeLLMProvider(),
        collector=collector,
    )

    assert state.status == "answered"
    assert state.final_answer
    assert state.legal_area == LegalArea.CONSUMER.value
    assert state.selected_context, "answered runs carry the selected sources (§13)"
    assert state.audit is not None and state.audit.passed
    assert any("não substitui" in c.lower() for c in state.caveats)
    # Per-step trace recorded for every executed node (§23).
    steps = [s.step for s in collector.for_run("run-answered")]
    assert steps[0] == "intake" and steps[-1] == "check_risks"
    assert "synthesize_answer" in steps and "audit_citations" in steps


# --- scenario 2: refused (out of scope) ---------------------------------------


def test_out_of_scope_question_is_refused_without_inventing(
    cdc_chunks: list[LegalChunk],
) -> None:
    service = _service(cdc_chunks)
    state = run_graph(
        "Qual a alíquota do imposto de renda sobre criptomoedas?",
        run_id="run-refused",
        search=service,
        llm=FakeLLMProvider(),
    )

    assert state.status == "refused"
    assert state.final_answer
    assert "999" not in (state.final_answer or "")
    # No statute was synthesized into the answer; nothing invented (§2.1, §2.2).
    assert state.draft_answer is None or state.legal_area != LegalArea.CONSUMER.value


# --- scenario 3: audit fail -> retry once -> conservative/refusal --------------


def test_audit_failure_retries_synthesis_once_then_settles(
    cdc_chunks: list[LegalChunk],
) -> None:
    service = _service(cdc_chunks)
    collector = TraceCollector()
    app = build_graph(search=service, llm=_HallucinatingLLM(), collector=collector)
    initial = LegalResearchState(
        run_id="run-retry", question="O fornecedor responde por defeito do produto?"
    )
    result = LegalResearchState.model_validate(app.invoke(initial))

    # The synthesis re-ran exactly once (one retry marker), per the §14 single-retry cap.
    assert retry_attempts(result.errors) == 1
    steps = [s.step for s in collector.for_run("run-retry")]
    assert steps.count("synthesize_answer") == 2
    assert "retry_synthesis" in steps
    # After the conservative second pass the hallucinated art. 999 is gone, and the
    # final state is internally consistent (audit passes) or it refused.
    assert "999" not in (result.final_answer or "")
    assert result.status in {"answered", "refused"}
    if result.status == "answered":
        assert result.audit is not None and result.audit.passed


# --- scenario 4: needs_more_info ----------------------------------------------


def test_vague_question_routes_to_needs_more_info(cdc_chunks: list[LegalChunk]) -> None:
    service = _service(cdc_chunks)
    state = run_graph(
        "ajuda?",
        run_id="run-nmi",
        search=service,
        llm=FakeLLMProvider(),
    )
    assert state.status == "needs_more_info"
    assert state.missing_facts
    assert state.final_answer


# --- standalone node tests ----------------------------------------------------


def test_intake_node_extracts_facts_and_missing() -> None:
    st = LegalResearchState(run_id="r", question="  Comprei um  produto com defeito? ")
    update = run_intake(st)
    assert update["question"] == "Comprei um produto com defeito?"
    assert "defeito" in update["facts"]["fact_cues"]
    assert update["missing_facts"] == []


def test_classify_area_node_consumer_vs_out_of_scope() -> None:
    assert classify_area("defeito do produto e direito do consumidor") is LegalArea.CONSUMER
    assert classify_area("alíquota de imposto sobre cripto") is LegalArea.TAX
    # In-scope areas (corpus ingested) carry no out-of-scope caveat.
    out = run_classify_area(
        LegalResearchState(run_id="r", question="alíquota de imposto sobre cripto")
    )
    assert out["legal_area"] == LegalArea.TAX.value
    assert "caveats" not in out
    # Administrative has no corpus → out of scope → caveat emitted.
    adm = run_classify_area(
        LegalResearchState(run_id="r", question="regras de licitação para servidor público")
    )
    assert adm["legal_area"] == LegalArea.ADMINISTRATIVE.value
    assert any("fora da cobertura" in c for c in adm["caveats"])


def test_retry_marker_counting_is_isolated() -> None:
    assert retry_attempts([]) == 0
    assert retry_attempts([RETRY_MARKER, "real error", RETRY_MARKER]) == 2


def test_answer_writer_node_populates_draft(cdc_chunks: list[LegalChunk]) -> None:
    from packages.agents._adapters import chunk_to_source

    service = _service(cdc_chunks)
    chunks = service.search("defeito do produto", 3, {"doc_type": "statute"})
    buffer = AnswerBuffer()
    node = make_answer_writer(FakeLLMProvider(), buffer)
    st = LegalResearchState(
        run_id="r",
        question="O fornecedor responde por defeito do produto?",
        selected_context=[chunk_to_source(c) for c in chunks],
    )
    update = node(st)
    assert update["draft_answer"]
    assert buffer.answer("r") is not None
