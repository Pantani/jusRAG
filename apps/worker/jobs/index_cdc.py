"""CLI job: index the CDC chunks into Qdrant.

``make index-cdc`` -> ``python -m apps.worker.jobs.index_cdc``.

Reads ``data/generated/cdc_chunks.jsonl`` (statutes) AND, when present,
``data/generated/case_law_chunks.jsonl`` (STJ case law, doc_type=case_law),
embeds each chunk with the configured ``EmbeddingProvider`` and upserts both into
the single ``legal_chunks`` Qdrant collection. The retriever then separates
statute from case_law via the ``doc_type`` metadata filter (§9/§22).

Idempotent: the point id is derived from the stable ``chunk_id`` (§28/§40.4), so
re-running after ``make ingest-cdc`` and ``ingest-case-law`` overwrites in place.
Requires a running Qdrant and a valid ``OPENAI_API_KEY``.
"""

from __future__ import annotations

import sys

from apps.worker.jobs.chunk_jsonl import load_indexable_chunks
from packages.config.settings import get_settings
from packages.embeddings.base import EmbeddingProvider
from packages.embeddings.openai_provider import OpenAIEmbeddingProvider
from packages.storage.base import VectorStore
from packages.storage.qdrant import QdrantVectorStore
from packages.storage.repositories import ChunkRepository

_OPENAI_EMBEDDING_DIM = 1536


def build_store(vector_size: int) -> VectorStore:
    settings = get_settings()
    return QdrantVectorStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection_legal_chunks,
        vector_size=vector_size,
    )


def run(embeddings: EmbeddingProvider, store: VectorStore) -> int:
    """Index all chunks; returns the number indexed."""

    chunks = load_indexable_chunks()
    repo = ChunkRepository(embeddings, store)
    return repo.index_chunks(chunks)


def main() -> int:
    embeddings: EmbeddingProvider = OpenAIEmbeddingProvider()
    store = build_store(_OPENAI_EMBEDDING_DIM)
    count = run(embeddings, store)
    print(f"Indexed {count} chunk(s) into Qdrant collection 'legal_chunks'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
