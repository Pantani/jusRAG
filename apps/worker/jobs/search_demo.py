"""CLI demo: run the acceptance search queries against the indexed corpus.

``make search-demo`` -> ``python -m apps.worker.jobs.search_demo``.

Runs fully offline and deterministically: the ``FakeEmbeddingProvider`` + the
in-memory vector store index the generated JSONL (statutes AND, when present,
STJ case law), then the ``LegalRetriever`` answers the acceptance queries.

Proves (Fase 3) "defeito do produto" -> art. 12 and "arrependimento" -> art. 49,
and (Fase 6 §22) that statute and case_law are retrieved as separate blocks:
"CDC aplica-se a banco/instituição financeira" surfaces STJ Súmula 297 in the
case_law block — without any network or running Qdrant.
"""

from __future__ import annotations

import sys

from apps.worker.jobs.chunk_jsonl import load_indexable_chunks
from packages.embeddings.fake_provider import FakeEmbeddingProvider
from packages.rag.retriever import LegalRetriever
from packages.rag.types import RetrievalQuery, RetrievedChunk
from packages.storage.memory import InMemoryVectorStore
from packages.storage.repositories import ChunkRepository

# Statute acceptance: filtered to doc_type=statute (Fase 3 acceptance).
DEMO_QUERIES: tuple[tuple[str, str], ...] = (
    ("defeito do produto", "12"),
    ("direito de arrependimento e desistência da compra", "49"),
    ("prazo para reclamar de vício", "26"),
)

# Separation acceptance (§22): same query, both blocks; case_law carries a súmula.
SEPARATED_QUERIES: tuple[tuple[str, str], ...] = (
    ("CDC aplica-se a banco e instituição financeira", "stj-sumula-297"),
)


def build_retriever() -> LegalRetriever:
    embeddings = FakeEmbeddingProvider()
    store = InMemoryVectorStore()
    ChunkRepository(embeddings, store).index_chunks(load_indexable_chunks())
    return LegalRetriever(embeddings, store)


def _format(hit: RetrievedChunk) -> str:
    label = hit.citation.article and f"art. {hit.citation.article}" or hit.citation.doc_type
    return f"{label} (chunk={hit.chunk_id}, score={hit.score:.3f})"


def _run_statute_queries(retriever: LegalRetriever) -> int:
    failures = 0
    for query, expected_article in DEMO_QUERIES:
        hits = retriever.retrieve(
            RetrievalQuery(query=query, top_k=3, legal_area="consumer", doc_type="statute")
        )
        top = hits[0] if hits else None
        ok = top is not None and top.citation.article == expected_article
        print(f"[{'OK' if ok else 'FAIL'}] statute query={query!r} -> art. {expected_article}")
        for hit in hits:
            print(f"        {_format(hit)}")
        failures += 0 if ok else 1
    return failures


def _run_separated_queries(retriever: LegalRetriever) -> int:
    failures = 0
    for query, expected_chunk in SEPARATED_QUERIES:
        blocks = retriever.retrieve_separated(
            RetrievalQuery(query=query, top_k=3, legal_area="consumer")
        )
        case_ids = {h.chunk_id for h in blocks.case_law}
        ok = bool(blocks.statutes) and expected_chunk in case_ids
        print(f"[{'OK' if ok else 'FAIL'}] separated query={query!r} -> case_law {expected_chunk}")
        print("        statutes:")
        for hit in blocks.statutes:
            print(f"          {_format(hit)}")
        print("        case_law:")
        for hit in blocks.case_law:
            print(f"          {_format(hit)}")
        failures += 0 if ok else 1
    return failures


def main() -> int:
    retriever = build_retriever()
    failures = _run_statute_queries(retriever) + _run_separated_queries(retriever)
    print()
    print("All acceptance queries passed." if failures == 0 else f"{failures} query(ies) failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
