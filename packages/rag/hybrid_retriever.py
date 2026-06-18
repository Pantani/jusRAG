"""Hybrid retrieval: dense vector + BM25 lexical fusion (§4, §38).

Default OFF (``Settings.enable_hybrid=False``) — when disabled, delegates 1:1 to
``LegalRetriever`` so the Phase-3 baseline is preserved bit-for-bit.

When enabled:
1. Run dense ``LegalRetriever`` and ``BM25Store.search`` over the same query.
2. Min-max normalize each set of raw scores into [0, 1] independently.
3. Combine ``w_semantic * dense + w_bm25 * lexical`` per chunk_id (dedup).
4. Re-run the composite legal ranking (§38) using the fused score in place of
   the bare semantic similarity. Authority and exact_citation_match terms keep
   their weights (0.20 / 0.10).

Normalization choice: min-max over the candidate pool. Rationale: BM25 raw
scores are unbounded and depend on corpus statistics, while cosine sits in
[-1, 1]; softmax would over-flatten the long tail of irrelevant lexical hits
and amplify near-ties at the top. Min-max keeps the relative spacing within
each modality and yields a stable [0, 1] mix usable by §38 weights.

Stays free of FastAPI/LLM coupling — only depends on the ``EmbeddingProvider``,
``VectorStore`` and ``BM25Store`` Protocols.
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.config.settings import Settings
from packages.embeddings.base import EmbeddingProvider
from packages.rag.legal_ranker import (
    AUTHORITY_WEIGHT,
    CITATION_WEIGHT,
    SEMANTIC_WEIGHT,
    authority_for_payload,
    exact_citation_match,
)
from packages.rag.query_analyzer import build_filters, extract_article
from packages.rag.retriever import LegalRetriever
from packages.rag.types import CitationRef, RetrievalQuery, RetrievedChunk
from packages.storage.base import VectorSearchResult, VectorStore
from packages.storage.opensearch import BM25SearchResult, BM25Store

_CANDIDATE_MULTIPLIER = 3
_MIN_CANDIDATES = 16


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _min_max(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    values = list(scores.values())
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        # All equal: assign a flat 1.0 so the modality still contributes
        # symmetrically instead of being zeroed out by a degenerate range.
        return {k: 1.0 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}


@dataclass(frozen=True)
class _Candidate:
    chunk_id: str
    text: str
    payload: dict[str, object]
    metadata: dict[str, object]
    semantic_raw: float
    bm25_raw: float


class HybridRetriever:
    """Semantic + BM25 retrieval; opt-in via ``Settings.enable_hybrid``."""

    def __init__(
        self,
        embeddings: EmbeddingProvider,
        store: VectorStore,
        settings: Settings,
        bm25: BM25Store | None = None,
    ) -> None:
        self._embeddings = embeddings
        self._store = store
        self._settings = settings
        self._bm25 = bm25
        self._dense = LegalRetriever(embeddings, store)

    def retrieve(self, request: RetrievalQuery) -> list[RetrievedChunk]:
        if not self._settings.enable_hybrid or self._bm25 is None:
            return self._dense.retrieve(request)

        query = request.query.strip()
        if not query:
            return []

        requested_article = extract_article(query)
        filters = build_filters(request) or None
        candidate_k = max(request.top_k * _CANDIDATE_MULTIPLIER, _MIN_CANDIDATES)

        query_vector = self._embeddings.embed_query(query)
        dense_hits = self._store.search(query_vector, candidate_k, filters)
        bm25_hits = self._bm25.search(query, candidate_k, filters)

        candidates = _merge_candidates(dense_hits, bm25_hits)
        return self._rank(candidates, request.top_k, requested_article)

    def _rank(
        self,
        candidates: dict[str, _Candidate],
        top_k: int,
        requested_article: str | None,
    ) -> list[RetrievedChunk]:
        sem_norm = _min_max({cid: c.semantic_raw for cid, c in candidates.items()})
        bm25_norm = _min_max({cid: c.bm25_raw for cid, c in candidates.items()})
        w_sem = self._settings.hybrid_semantic_weight
        w_bm = self._settings.hybrid_bm25_weight

        ranked: list[RetrievedChunk] = []
        for cid, cand in candidates.items():
            hybrid = _clamp01(w_sem * sem_norm.get(cid, 0.0) + w_bm * bm25_norm.get(cid, 0.0))
            authority = authority_for_payload(cand.payload)
            citation = exact_citation_match(cand.payload, requested_article)
            score = (
                SEMANTIC_WEIGHT * hybrid
                + AUTHORITY_WEIGHT * authority
                + CITATION_WEIGHT * citation
            )
            ranked.append(_to_chunk(cand, score, hybrid))

        ranked.sort(key=lambda r: (-r.score, r.chunk_id))
        return ranked[:top_k]


def _merge_candidates(
    dense_hits: list[VectorSearchResult],
    bm25_hits: list[BM25SearchResult],
) -> dict[str, _Candidate]:
    out: dict[str, _Candidate] = {}
    for dense in dense_hits:
        out[dense.chunk_id] = _Candidate(
            chunk_id=dense.chunk_id,
            text=dense.text,
            payload=dense.payload,
            metadata=dict(dense.metadata),
            semantic_raw=_clamp01(dense.score),
            bm25_raw=0.0,
        )
    for lex in bm25_hits:
        existing = out.get(lex.chunk_id)
        if existing is None:
            out[lex.chunk_id] = _Candidate(
                chunk_id=lex.chunk_id,
                text=lex.text,
                payload=lex.payload,
                metadata=dict(lex.metadata),
                semantic_raw=0.0,
                bm25_raw=lex.score,
            )
        else:
            out[lex.chunk_id] = _Candidate(
                chunk_id=existing.chunk_id,
                text=existing.text,
                payload=existing.payload,
                metadata=existing.metadata,
                semantic_raw=existing.semantic_raw,
                bm25_raw=lex.score,
            )
    return out


def _to_chunk(cand: _Candidate, score: float, hybrid_semantic: float) -> RetrievedChunk:
    payload = cand.payload
    citation = CitationRef(
        title=str(payload.get("title", "")),
        article=payload.get("article"),  # type: ignore[arg-type]
        source_url=payload.get("source_url"),  # type: ignore[arg-type]
        chunk_id=cand.chunk_id,
        doc_type=str(payload.get("doc_type", "")),
        source=str(payload.get("source", "")),
    )
    return RetrievedChunk(
        chunk_id=cand.chunk_id,
        text=cand.text,
        score=score,
        semantic_score=hybrid_semantic,
        citation=citation,
        metadata=dict(cand.metadata),
    )


__all__ = ["HybridRetriever"]
