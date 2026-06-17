"""Legal retriever (§29).

Pipeline: query analysis -> embed query -> vector search (with metadata filters)
-> composite legal ranking (§38) -> RetrievedChunk list. Depends only on the
``EmbeddingProvider`` and ``VectorStore`` Protocols, so the fake provider + the
in-memory store drive it in tests with no network.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from packages.embeddings.base import EmbeddingProvider
from packages.legal_types.enums import DocType
from packages.rag.legal_ranker import composite_score
from packages.rag.query_analyzer import build_filters, extract_article
from packages.rag.types import CitationRef, RetrievalQuery, RetrievedChunk
from packages.storage.base import VectorSearchResult, VectorStore

# Over-fetch from the vector layer, then re-rank, then truncate to top_k.
_CANDIDATE_MULTIPLIER = 3
_MIN_CANDIDATES = 16


@dataclass(frozen=True)
class SeparatedRetrieval:
    """Retrieval split into legislation vs jurisprudence blocks (§4/§22).

    The answer layer renders ``statutes`` under "Fundamento legal" and
    ``case_law`` under "Jurisprudência relevante", keeping the two sources
    visibly separated (system rule §2.4). ``case_law`` is empty when no
    jurisprudence source was retrieved — it is never fabricated (§22).
    """

    statutes: list[RetrievedChunk]
    case_law: list[RetrievedChunk]


class LegalRetriever:
    """Retrieves and ranks statute/case-law chunks for a legal query."""

    def __init__(self, embeddings: EmbeddingProvider, store: VectorStore) -> None:
        self._embeddings = embeddings
        self._store = store

    def retrieve(self, request: RetrievalQuery) -> list[RetrievedChunk]:
        query = request.query.strip()
        if not query:
            return []

        requested_article = extract_article(query)
        filters = build_filters(request)
        query_vector = self._embeddings.embed_query(query)

        candidate_k = max(request.top_k * _CANDIDATE_MULTIPLIER, _MIN_CANDIDATES)
        hits = self._store.search(query_vector, candidate_k, filters or None)

        ranked: list[RetrievedChunk] = []
        for hit in hits:
            score, semantic = composite_score(hit, requested_article)
            ranked.append(_to_retrieved_chunk(hit, score, semantic))

        ranked.sort(key=lambda r: r.score, reverse=True)
        return ranked[: request.top_k]

    def retrieve_separated(self, request: RetrievalQuery) -> SeparatedRetrieval:
        """Retrieve statutes and case_law in distinct ranked blocks (§4/§22).

        Runs two independent doc_type-filtered retrievals so each block is ranked
        and truncated to ``top_k`` on its own — a statute-heavy result can't crowd
        jurisprudence out, and vice-versa. ``case_law`` stays empty when no
        jurisprudence source exists for the query.
        """

        statutes = self.retrieve(_with_doc_type(request, DocType.STATUTE))
        case_law = self.retrieve(_with_doc_type(request, DocType.CASE_LAW))
        return SeparatedRetrieval(statutes=statutes, case_law=case_law)


def _with_doc_type(request: RetrievalQuery, doc_type: DocType) -> RetrievalQuery:
    filters = {**request.filters, "doc_type": str(doc_type)}
    return replace(request, doc_type=str(doc_type), filters=filters)


def _to_retrieved_chunk(hit: VectorSearchResult, score: float, semantic: float) -> RetrievedChunk:
    payload = hit.payload
    citation = CitationRef(
        title=str(payload.get("title", "")),
        article=payload.get("article"),
        source_url=payload.get("source_url"),
        chunk_id=hit.chunk_id,
        doc_type=str(payload.get("doc_type", "")),
        source=str(payload.get("source", "")),
    )
    return RetrievedChunk(
        chunk_id=hit.chunk_id,
        text=hit.text,
        score=score,
        semantic_score=semantic,
        citation=citation,
        metadata=dict(hit.metadata),
    )
