"""CLI job: index the CDC chunks into Qdrant.

``make index-cdc`` -> ``python -m apps.worker.jobs.index_cdc``.

Reads ``data/generated/cdc_chunks.jsonl`` (statutes) AND, when present,
``data/generated/case_law_chunks.jsonl`` (STJ case law, doc_type=case_law),
embeds each chunk with the configured ``EmbeddingProvider`` and upserts both into
the single ``legal_chunks`` Qdrant collection. The retriever then separates
statute from case_law via the ``doc_type`` metadata filter (§9/§22).

Idempotent: the point id is derived from the stable ``chunk_id`` (§28/§40.4), so
re-running after ``make ingest-cdc`` and ``ingest-case-law`` overwrites in place.

The embedding provider follows ``EMBEDDING_PROVIDER``: ``openai`` (default) requires
a running Qdrant and a valid ``OPENAI_API_KEY`` (no silent fallback); ``fake`` lets
``EMBEDDING_PROVIDER=fake make index-cdc`` index deterministic vectors into the real
Qdrant with no key. The collection vector size always matches the selected provider —
switching providers on an existing ``legal_chunks`` collection requires recreating it.
"""

from __future__ import annotations

import sys

from apps.worker.jobs.chunk_jsonl import load_indexable_chunks
from packages.config.settings import get_settings
from packages.embeddings.base import EmbeddingProvider
from packages.embeddings.selector import embedding_vector_size, make_embedding_provider
from packages.storage.base import VectorStore
from packages.storage.qdrant import QdrantVectorStore
from packages.storage.repositories import ChunkRepository


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
    settings = get_settings()
    embeddings = make_embedding_provider(settings)
    store = build_store(embedding_vector_size(settings))
    count = run(embeddings, store)
    print(f"Indexed {count} chunk(s) into Qdrant collection 'legal_chunks'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
