"""CLI demo: answer legal questions with cited sources (``make ask-demo``).

``make ask-demo`` -> ``python -m apps.worker.jobs.ask_demo``.

Runs fully offline and deterministically: the ``FakeEmbeddingProvider`` + the
in-memory store index the generated CDC JSONL, and the ``FakeLLMProvider`` writes
the structured answer strictly from the retrieved context.

The demo drives the **same agentic runtime as the product** (``packages.agents``
LangGraph), not the AnswerWriter directly, so the showcase reflects the real flow:
intake → ``LegalAreaClassifier`` (scope gate, §15.2) → retrieval (filtered by the
classified ``legal_area``) → synthesis → audit → risk. That gives a robust
out-of-scope refusal (a tax question never falls back to an irrelevant consumer
súmula) on top of the AnswerWriter's empty-retrieval gate. Demonstrates a cited
in-scope answer (defeito do produto -> art. 12), the right-of-withdrawal answer
(arrependimento -> art. 49), a case-law block separated from the legal basis
(CDC aplica-se a banco -> STJ Súmula 297), and a safe refusal for an out-of-scope
question (imposto sobre cripto -> status=refused, nothing invented).
"""

from __future__ import annotations

import sys

from apps.worker.jobs.chunk_jsonl import load_case_law_chunks, load_chunks
from packages.agents.answer_writer import AnswerBuffer
from packages.agents.graph import build_graph
from packages.agents.state import LegalResearchState
from packages.answer.schemas import AnswerResponse
from packages.embeddings.fake_provider import FakeEmbeddingProvider
from packages.llm.fake_provider import FakeLLMProvider
from packages.rag.retriever import LegalRetriever
from packages.rag.search_service import SearchService
from packages.storage.memory import InMemoryVectorStore
from packages.storage.repositories import ChunkRepository

DEMO_QUESTIONS: tuple[str, ...] = (
    "O fornecedor responde por defeito do produto?",
    "O consumidor tem direito de arrependimento na compra online?",
    "O CDC se aplica a banco e instituição financeira?",
    "Qual a alíquota do imposto de renda sobre criptomoedas?",
)


class DemoRuntime:
    """Runs the agentic graph offline, exposing both the §13 state and the answer."""

    def __init__(self) -> None:
        embeddings = FakeEmbeddingProvider()
        store = InMemoryVectorStore()
        chunks = load_chunks() + load_case_law_chunks()
        ChunkRepository(embeddings, store).index_chunks(chunks)
        search = SearchService(LegalRetriever(embeddings, store))
        self._buffer = AnswerBuffer()
        self._app = build_graph(
            search=search, llm=FakeLLMProvider(), buffer=self._buffer
        )

    def ask(self, question: str, run_id: str) -> tuple[LegalResearchState, AnswerResponse | None]:
        initial = LegalResearchState(run_id=run_id, question=question)
        state = LegalResearchState.model_validate(self._app.invoke(initial))
        return state, self._buffer.answer(run_id)


def _print_answer(
    question: str, state: LegalResearchState, answer: AnswerResponse | None
) -> None:
    print(f"PERGUNTA: {question}")
    print(f"  status: {state.status}")
    short = answer.short_answer if answer is not None else (state.final_answer or "")
    print(f"  short_answer: {short}")
    for basis in answer.legal_basis if answer is not None else []:
        print(f"  legal_basis: {basis.text}  citations={basis.citations}")
    for case in answer.case_law if answer is not None else []:
        print(
            f"  case_law: {case.court} {case.case_number} -> {case.ementa}  "
            f"source_url={case.source_url}"
        )
    sources = [s.chunk_id for s in answer.sources] if answer is not None else []
    print(f"  sources: {sources}")
    if answer is not None and answer.audit is not None:
        print(
            f"  audit: coverage={answer.audit.citation_coverage:.2f} "
            f"unsupported_rate={answer.audit.unsupported_legal_claim_rate:.2f} "
            f"passed={answer.audit.passed}"
        )
    print("  not_legal_advice: True")
    print()


def main() -> int:
    runtime = DemoRuntime()
    for i, question in enumerate(DEMO_QUESTIONS):
        state, answer = runtime.ask(question, run_id=f"ask-demo-{i}")
        _print_answer(question, state, answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
