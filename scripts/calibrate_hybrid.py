"""Calibrate hybrid retrieval weights against the golden 158q set (Tarefa 13.C.4).

Transient harness — NOT shipped in packages/. Embeds every golden in-scope query
once with the configured EmbeddingProvider (OpenAI by default for C.4), caches
the vector, then for each ``semantic_weight`` in the grid:

1. Fuses the dense Qdrant hits with the BM25 OpenSearch hits via the same
   normalization the HybridRetriever uses (min-max per modality).
2. Reuses the §38 ranking (semantic→hybrid substitution, authority+citation
   constants preserved) by directly invoking HybridRetriever._rank-equivalent
   logic — but reusing the cached query vectors so we pay 1 embedding/query
   total instead of 1/query/weight.
3. Computes recall@5 and precision@5 micro-averaged over in-scope questions.

Outputs a Markdown table to stdout and the chosen winning weights given the
decision rule (Δrecall ≥ 0.02 vs semantic-only baseline at the same provider).

Run:
    EMBEDDING_PROVIDER=openai OPENAI_API_KEY=sk-... \
    OPENSEARCH_URL=http://localhost:9200 QDRANT_URL=http://localhost:6333 \
    python -m scripts.calibrate_hybrid
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from apps.worker.jobs.chunk_jsonl import load_indexable_chunks  # noqa: F401  (preload validation)
from packages.config.settings import get_settings
from packages.embeddings.selector import embedding_vector_size, make_embedding_provider
from packages.evals.golden import in_scope_questions, load_golden
from packages.rag.legal_ranker import (
    AUTHORITY_WEIGHT,
    CITATION_WEIGHT,
    SEMANTIC_WEIGHT,
    authority_for_payload,
    exact_citation_match,
)
from packages.rag.query_analyzer import build_filters, extract_article
from packages.rag.types import RetrievalQuery
from packages.storage.opensearch import OpenSearchBM25Store
from packages.storage.qdrant import QdrantVectorStore

GRID = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]
TOP_K = 5
CANDIDATE_K = max(TOP_K * 3, 16)


@dataclass
class GridRow:
    semantic_weight: float
    bm25_weight: float
    recall_at_5: float
    precision_at_5: float


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _min_max(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    lo, hi = min(scores.values()), max(scores.values())
    if hi - lo < 1e-12:
        return dict.fromkeys(scores, 1.0)
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}


def _semantic_only_rank(
    dense_hits: list,
    requested_article: str | None,
    top_k: int,
) -> list[str]:
    ranked: list[tuple[str, float]] = []
    for hit in dense_hits:
        sem = _clamp01(hit.score)
        score = (
            SEMANTIC_WEIGHT * sem
            + AUTHORITY_WEIGHT * authority_for_payload(hit.payload)
            + CITATION_WEIGHT * exact_citation_match(hit.payload, requested_article)
        )
        ranked.append((hit.chunk_id, score))
    ranked.sort(key=lambda t: (-t[1], t[0]))
    return [cid for cid, _ in ranked[:top_k]]


def _hybrid_rank(
    dense_hits: list,
    bm25_hits: list,
    w_sem: float,
    w_bm: float,
    requested_article: str | None,
    top_k: int,
) -> list[str]:
    cand: dict[str, dict] = {}
    for h in dense_hits:
        cand[h.chunk_id] = {
            "payload": h.payload,
            "sem": _clamp01(h.score),
            "bm": 0.0,
        }
    for h in bm25_hits:
        slot = cand.setdefault(h.chunk_id, {"payload": h.payload, "sem": 0.0, "bm": 0.0})
        slot["bm"] = h.score
        if not slot["payload"]:
            slot["payload"] = h.payload

    sem_norm = _min_max({cid: c["sem"] for cid, c in cand.items()})
    bm_norm = _min_max({cid: c["bm"] for cid, c in cand.items()})

    ranked: list[tuple[str, float]] = []
    for cid, c in cand.items():
        hybrid = _clamp01(w_sem * sem_norm.get(cid, 0.0) + w_bm * bm_norm.get(cid, 0.0))
        score = (
            SEMANTIC_WEIGHT * hybrid
            + AUTHORITY_WEIGHT * authority_for_payload(c["payload"])
            + CITATION_WEIGHT * exact_citation_match(c["payload"], requested_article)
        )
        ranked.append((cid, score))
    ranked.sort(key=lambda t: (-t[1], t[0]))
    return [cid for cid, _ in ranked[:top_k]]


def main() -> int:
    settings = get_settings()
    embeddings = make_embedding_provider(settings)
    vector_size = embedding_vector_size(settings)
    qdrant = QdrantVectorStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection_legal_chunks,
        vector_size=vector_size,
    )
    bm25 = OpenSearchBM25Store(
        url=os.environ.get("OPENSEARCH_URL", settings.opensearch_url)
    )

    questions = in_scope_questions(load_golden())
    print(
        f"Calibrating over {len(questions)} in-scope golden questions; "
        f"provider={settings.embedding_provider}, top_k={TOP_K}, candidate_k={CANDIDATE_K}",
        file=sys.stderr,
    )

    # 1 embedding per question, reused across all grid weights.
    cache: list[tuple[str, str | None, dict, list, list]] = []
    for q in questions:
        req = RetrievalQuery(query=q.question, top_k=TOP_K)
        requested = extract_article(q.question)
        filters = build_filters(req) or None
        vec = embeddings.embed_query(q.question)
        dense = qdrant.search(vec, CANDIDATE_K, filters)
        lex = bm25.search(q.question, CANDIDATE_K, filters)
        cache.append((q.id, requested, {f"expected:{q.id}": q.expected_chunk_ids}, dense, lex))

    # Build a parallel list keyed by index so we don't reembed.
    expected_by_id = {q.id: set(q.expected_chunk_ids) for q in questions}

    # Baseline (semantic-only) for sanity check.
    sem_hits_total = 0
    sem_expected_total = 0
    sem_retrieved_total = 0
    for case in cache:
        qid, requested, _, dense, _ = case
        retrieved = _semantic_only_rank(dense, requested, TOP_K)
        expected = expected_by_id[qid]
        sem_hits_total += sum(1 for cid in retrieved if cid in expected)
        sem_expected_total += len(expected)
        sem_retrieved_total += len(retrieved)
    sem_recall = sem_hits_total / sem_expected_total if sem_expected_total else 1.0
    sem_precision = sem_hits_total / sem_retrieved_total if sem_retrieved_total else 0.0
    print(
        f"\nSemantic-only baseline (provider={settings.embedding_provider}): "
        f"recall@5={sem_recall:.4f}  precision@5={sem_precision:.4f}",
        file=sys.stderr,
    )

    rows: list[GridRow] = []
    for w_sem in GRID:
        w_bm = round(1.0 - w_sem, 6)
        hits_total = 0
        expected_total = 0
        retrieved_total = 0
        for case in cache:
            qid, requested, _, dense, lex = case
            retrieved = _hybrid_rank(dense, lex, w_sem, w_bm, requested, TOP_K)
            expected = expected_by_id[qid]
            hits_total += sum(1 for cid in retrieved if cid in expected)
            expected_total += len(expected)
            retrieved_total += len(retrieved)
        recall = hits_total / expected_total if expected_total else 1.0
        precision = hits_total / retrieved_total if retrieved_total else 0.0
        rows.append(GridRow(w_sem, w_bm, recall, precision))

    print("\n| semantic_weight | bm25_weight | recall@5 | precision@5 | Δrecall vs sem-only |")
    print("|---|---|---|---|---|")
    for r in rows:
        delta = r.recall_at_5 - sem_recall
        print(
            f"| {r.semantic_weight:.2f} | {r.bm25_weight:.2f} | "
            f"{r.recall_at_5:.4f} | {r.precision_at_5:.4f} | {delta:+.4f} |"
        )

    best = max(rows, key=lambda r: (r.recall_at_5, r.precision_at_5))
    delta = best.recall_at_5 - sem_recall
    print(
        f"\nBest weights: semantic={best.semantic_weight:.2f}, bm25={best.bm25_weight:.2f}, "
        f"recall@5={best.recall_at_5:.4f}, Δ={delta:+.4f}"
    )

    if delta >= 0.02:
        print(
            f"\nDECISION: ACTIVATE hybrid as default (Δrecall {delta:+.4f} ≥ +0.0200). "
            f"Set hybrid_semantic_weight={best.semantic_weight:.2f}, "
            f"hybrid_bm25_weight={best.bm25_weight:.2f}, enable_hybrid=True."
        )
    else:
        print(
            f"\nDECISION: KEEP hybrid OPT-IN (Δrecall {delta:+.4f} < +0.0200). "
            f"Update opt-in defaults to semantic={best.semantic_weight:.2f}, "
            f"bm25={best.bm25_weight:.2f} (best within grid) for informed adopters."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
