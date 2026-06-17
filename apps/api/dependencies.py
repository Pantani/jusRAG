"""FastAPI dependency providers.

Kept minimal for Phase 1. Downstream phases inject the embedding provider, vector
store, LLM provider and repositories here, always behind their `Protocol`s (§6 of
the system rules).
"""

from typing import Annotated

from fastapi import Depends

from packages.answer.answer_writer import AnswerWriter
from packages.config.settings import Settings, get_settings
from packages.embeddings.base import EmbeddingProvider
from packages.embeddings.openai_provider import OpenAIEmbeddingProvider
from packages.llm.base import LLMProvider
from packages.llm.openai_provider import OpenAILLMProvider
from packages.rag.retriever import LegalRetriever
from packages.rag.search_service import SearchService
from packages.storage.base import VectorStore
from packages.storage.qdrant import QdrantVectorStore

SettingsDep = Annotated[Settings, Depends(get_settings)]

# OpenAI text-embedding-3-small dimensionality (real provider).
_OPENAI_EMBEDDING_DIM = 1536


def get_embedding_provider(settings: SettingsDep) -> EmbeddingProvider:
    """Real embedding provider. Overridden by the fake in tests (no network)."""

    return OpenAIEmbeddingProvider(settings)


def get_vector_store(settings: SettingsDep) -> VectorStore:
    """Real Qdrant store. Overridden by the in-memory store in tests."""

    return QdrantVectorStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection_legal_chunks,
        vector_size=_OPENAI_EMBEDDING_DIM,
    )


EmbeddingProviderDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
VectorStoreDep = Annotated[VectorStore, Depends(get_vector_store)]


def get_search_service(embeddings: EmbeddingProviderDep, store: VectorStoreDep) -> SearchService:
    return SearchService(LegalRetriever(embeddings, store))


SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]


def get_llm_provider(settings: SettingsDep) -> LLMProvider:
    """Real LLM provider. Overridden by the fake in tests (no network)."""

    return OpenAILLMProvider(settings)


LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]


def get_answer_writer(service: SearchServiceDep, llm: LLMProviderDep) -> AnswerWriter:
    return AnswerWriter(service, llm)


AnswerWriterDep = Annotated[AnswerWriter, Depends(get_answer_writer)]

__all__ = [
    "AnswerWriterDep",
    "EmbeddingProviderDep",
    "LLMProviderDep",
    "SearchServiceDep",
    "SettingsDep",
    "VectorStoreDep",
    "get_answer_writer",
    "get_embedding_provider",
    "get_llm_provider",
    "get_search_service",
    "get_settings",
    "get_vector_store",
]
