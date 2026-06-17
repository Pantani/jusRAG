"""Offline eval harness: builds the real RAG pipeline on the seed corpus (§35).

Wires the *real* retriever, search service and answer writer over deterministic
fakes (``FakeEmbeddingProvider`` + ``InMemoryVectorStore`` + ``FakeLLMProvider``)
indexed with the seed chunks. No network, fully reproducible — this is the CI path.
Each eval module consumes this harness so retrieval, citation and answer metrics are
measured against the same pipeline a request would traverse.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.worker.jobs.chunk_jsonl import load_indexable_chunks
from packages.answer.answer_writer import AnswerWriter
from packages.embeddings.fake_provider import FakeEmbeddingProvider
from packages.llm.fake_provider import FakeLLMProvider
from packages.rag.retriever import LegalRetriever
from packages.rag.search_service import SearchService
from packages.storage.memory import InMemoryVectorStore
from packages.storage.repositories import ChunkRepository


@dataclass(frozen=True)
class EvalHarness:
    """The assembled, indexed offline pipeline."""

    search: SearchService
    answer_writer: AnswerWriter
    indexed_count: int


def build_harness() -> EvalHarness:
    """Index the seed corpus into an in-memory pipeline driven by fakes."""

    embeddings = FakeEmbeddingProvider()
    store = InMemoryVectorStore()
    count = ChunkRepository(embeddings, store).index_chunks(load_indexable_chunks())
    search = SearchService(LegalRetriever(embeddings, store))
    answer_writer = AnswerWriter(search, FakeLLMProvider())
    return EvalHarness(search=search, answer_writer=answer_writer, indexed_count=count)
