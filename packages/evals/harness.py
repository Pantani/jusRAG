"""Offline eval harness: builds the real RAG pipeline on the seed corpus (§35).

Wires the *real* retriever, search service and answer writer over deterministic
fakes (``FakeEmbeddingProvider`` + ``InMemoryVectorStore`` + ``FakeLLMProvider``)
indexed with the seed chunks. No network, fully reproducible — this is the CI path.
Each eval module consumes this harness so retrieval, citation and answer metrics are
measured against the same pipeline a request would traverse.

A second constructor — :func:`build_real_harness` — wires the same pipeline against
*real* providers (OpenAI / local sentence-transformers / Ollama) and a *real* Qdrant
collection. It is opt-in (``make eval-real``) and never used by CI.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.worker.jobs.chunk_jsonl import load_indexable_chunks
from packages.answer.answer_writer import AnswerWriter
from packages.config.settings import Settings, get_settings
from packages.embeddings.base import EmbeddingProvider
from packages.embeddings.fake_provider import FakeEmbeddingProvider
from packages.embeddings.selector import embedding_vector_size, make_embedding_provider
from packages.llm.base import LLMProvider
from packages.llm.fake_provider import FakeLLMProvider
from packages.llm.selector import make_llm_provider
from packages.rag.hybrid_retriever import make_retriever
from packages.rag.search_service import SearchService
from packages.storage.base import VectorStore
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

    embeddings: EmbeddingProvider = FakeEmbeddingProvider()
    store: VectorStore = InMemoryVectorStore()
    llm: LLMProvider = FakeLLMProvider()
    return _assemble(embeddings, store, llm, get_settings())


def build_real_harness(settings: Settings | None = None) -> EvalHarness:
    """Wire the eval pipeline against the providers selected by ``settings``.

    Embedding + Vector store + LLM come from the real selectors. The collection
    is pre-flight-validated for vector-size compatibility against the provider
    in :func:`packages.evals.run_all._preflight_qdrant`; this function assumes
    that validation has passed (or is being delegated to it).
    """

    settings = settings or get_settings()
    embeddings = make_embedding_provider(settings)
    # Lazy import keeps unit tests from requiring qdrant_client.
    from packages.storage.qdrant import QdrantVectorStore

    store = QdrantVectorStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection_legal_chunks,
        vector_size=embedding_vector_size(settings),
    )
    llm = make_llm_provider(settings)
    return _assemble(embeddings, store, llm, settings)


def _assemble(
    embeddings: EmbeddingProvider,
    store: VectorStore,
    llm: LLMProvider,
    settings: Settings,
) -> EvalHarness:
    count = ChunkRepository(embeddings, store).index_chunks(load_indexable_chunks())
    search = SearchService(make_retriever(embeddings, store, settings))
    answer_writer = AnswerWriter(search, llm)
    return EvalHarness(search=search, answer_writer=answer_writer, indexed_count=count)
