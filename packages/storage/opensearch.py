"""BM25 lexical store — protocol + fake offline adapter + real stub.

Two layers:

- ``BM25Store`` (Protocol): the boundary the hybrid retriever consumes. Mirrors
  ``VectorStore.search`` shape so ranking treats both signals symmetrically.
- ``FakeBM25Store``: deterministic, in-memory TF-IDF over indexed chunks — no
  network. Used by unit tests and offline demos so hybrid retrieval is exercised
  in CI without an OpenSearch container.
- ``OpenSearchBM25Store``: thin stub. Real implementation lands when the
  OpenSearch container is wired (see ``Settings.enable_opensearch``); raises
  ``NotImplementedError`` so no false signal leaks into ranking.

Scores are non-negative; the hybrid layer normalizes them to [0, 1] before
fusing with the semantic score.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from packages.legal_types.schemas import LegalChunk
from packages.storage.payload import chunk_to_payload, payload_matches_filters

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


@dataclass(frozen=True)
class BM25SearchResult:
    """A single BM25 hit. Shape parallels ``VectorSearchResult`` (§28)."""

    chunk_id: str
    score: float
    text: str
    payload: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class BM25Store(Protocol):
    """Lexical store: index chunks and search by raw query string."""

    def index_chunks(self, chunks: list[LegalChunk]) -> None: ...

    def search(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[BM25SearchResult]: ...


class FakeBM25Store:
    """Deterministic TF-IDF lexical store for offline tests/demos.

    Not full BM25 (no length normalization / k1,b tuning) — but stable, side-
    effect-free and good enough to (a) reward exact term matches (e.g. "art. 14")
    that pure dense embeddings can blur, and (b) prove the fusion code path.
    """

    def __init__(self) -> None:
        self._payloads: dict[str, dict[str, Any]] = {}
        self._tokens: dict[str, list[str]] = {}
        self._df: dict[str, int] = {}

    def index_chunks(self, chunks: list[LegalChunk]) -> None:
        for chunk in chunks:
            payload = chunk_to_payload(chunk)
            tokens = _tokenize(chunk.text)
            previous = self._tokens.get(chunk.chunk_id)
            if previous is not None:
                for tok in set(previous):
                    self._df[tok] = max(0, self._df.get(tok, 0) - 1)
                    if self._df[tok] == 0:
                        del self._df[tok]
            self._payloads[chunk.chunk_id] = payload
            self._tokens[chunk.chunk_id] = tokens
            for tok in set(tokens):
                self._df[tok] = self._df.get(tok, 0) + 1

    def __len__(self) -> int:
        return len(self._payloads)

    def _idf(self, term: str) -> float:
        n = len(self._payloads)
        df = self._df.get(term, 0)
        if df == 0 or n == 0:
            return 0.0
        return math.log((1.0 + n) / (1.0 + df)) + 1.0

    def search(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[BM25SearchResult]:
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        scored: list[BM25SearchResult] = []
        for chunk_id, payload in self._payloads.items():
            if not payload_matches_filters(payload, filters):
                continue
            tokens = self._tokens[chunk_id]
            if not tokens:
                continue
            score = self._score(q_tokens, tokens)
            if score <= 0.0:
                continue
            scored.append(
                BM25SearchResult(
                    chunk_id=chunk_id,
                    score=score,
                    text=payload["text"],
                    payload=payload,
                    metadata=dict(payload.get("metadata", {})),
                )
            )
        scored.sort(key=lambda r: (-r.score, r.chunk_id))
        return scored[:top_k]

    def _score(self, q_tokens: list[str], doc_tokens: list[str]) -> float:
        # TF (raw count) * IDF, summed per unique query term.
        tf: dict[str, int] = {}
        for tok in doc_tokens:
            tf[tok] = tf.get(tok, 0) + 1
        score = 0.0
        for term in set(q_tokens):
            if term in tf:
                score += tf[term] * self._idf(term)
        return score


class OpenSearchBM25Store:
    """Real OpenSearch BM25 adapter — thin httpx-based client.

    Indexes payloads identical to the Qdrant store (via ``chunk_to_payload``) so
    hybrid fusion can dedup by ``chunk_id`` symmetrically with the dense path.
    Search uses ``multi_match`` over ``text^2 + title`` with the OpenSearch
    default Portuguese-friendly ``standard`` analyzer — TODO(foundation): swap
    to ``analysis-icu`` / pt-stemmer plugin before non-local use.

    Filters are translated into ``term`` clauses inside a ``bool.filter`` on
    keyword sub-fields (``<key>.keyword``); ``payload_matches_filters`` semantics
    is preserved (equality + list-of-allowed-values via ``terms``).
    """

    _INDEX_SETTINGS: dict[str, Any] = {
        "settings": {
            "index": {"number_of_shards": 1, "number_of_replicas": 0},
            "analysis": {"analyzer": {"default": {"type": "standard"}}},
        },
        "mappings": {
            "dynamic": True,
            "properties": {
                "chunk_id": {"type": "keyword"},
                "text": {"type": "text"},
                "title": {"type": "text"},
                "doc_type": {"type": "keyword"},
                "legal_area": {"type": "keyword"},
                "source": {"type": "keyword"},
                "article": {"type": "keyword"},
                "norm_number": {"type": "keyword"},
                "norm_year": {"type": "keyword"},
                "is_current": {"type": "boolean"},
            },
        },
    }

    def __init__(
        self,
        url: str,
        index: str = "legal_chunks",
        *,
        timeout: float = 10.0,
    ) -> None:
        import httpx  # local import keeps unit tests free of network deps

        self._base = url.rstrip("/")
        self._index = index
        self._client = httpx.Client(base_url=self._base, timeout=timeout)
        self._ensure_index()

    def _ensure_index(self) -> None:
        r = self._client.head(f"/{self._index}")
        if r.status_code == 200:
            return
        if r.status_code != 404:
            raise RuntimeError(
                f"OpenSearch HEAD /{self._index} returned {r.status_code}: {r.text[:200]!r}"
            )
        create = self._client.put(f"/{self._index}", json=self._INDEX_SETTINGS)
        if create.status_code >= 300:
            raise RuntimeError(
                f"OpenSearch index create failed ({create.status_code}): {create.text[:200]!r}"
            )

    def recreate_index(self) -> None:
        """Drop and recreate the index — destructive, only for indexing jobs."""

        self._client.delete(f"/{self._index}")
        create = self._client.put(f"/{self._index}", json=self._INDEX_SETTINGS)
        if create.status_code >= 300:
            raise RuntimeError(
                f"OpenSearch index create failed ({create.status_code}): {create.text[:200]!r}"
            )

    def index_chunks(self, chunks: list[LegalChunk]) -> None:
        if not chunks:
            return
        lines: list[str] = []
        import json as _json

        for chunk in chunks:
            payload = chunk_to_payload(chunk)
            lines.append(
                _json.dumps({"index": {"_index": self._index, "_id": chunk.chunk_id}})
            )
            lines.append(_json.dumps(payload, ensure_ascii=False))
        body = "\n".join(lines) + "\n"
        r = self._client.post(
            "/_bulk",
            content=body.encode("utf-8"),
            headers={"Content-Type": "application/x-ndjson"},
        )
        if r.status_code >= 300:
            raise RuntimeError(f"OpenSearch bulk failed ({r.status_code}): {r.text[:300]!r}")
        data = r.json()
        if data.get("errors"):
            first = next(
                (it for it in data.get("items", []) if "error" in it.get("index", {})),
                None,
            )
            raise RuntimeError(f"OpenSearch bulk reported errors; first: {first!r}")
        # Force refresh so subsequent searches see the docs.
        self._client.post(f"/{self._index}/_refresh")

    def search(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[BM25SearchResult]:
        must: dict[str, Any] = {
            "multi_match": {
                "query": query,
                "fields": ["text^2", "title"],
                "type": "best_fields",
            }
        }
        bool_query: dict[str, Any] = {"must": [must]}
        if filters:
            bool_query["filter"] = _build_filter_clauses(filters)
        body = {"size": top_k, "query": {"bool": bool_query}}
        r = self._client.post(f"/{self._index}/_search", json=body)
        if r.status_code >= 300:
            raise RuntimeError(f"OpenSearch search failed ({r.status_code}): {r.text[:200]!r}")
        hits = r.json().get("hits", {}).get("hits", [])
        out: list[BM25SearchResult] = []
        for hit in hits:
            payload = hit.get("_source", {})
            out.append(
                BM25SearchResult(
                    chunk_id=str(payload.get("chunk_id", hit.get("_id", ""))),
                    score=float(hit.get("_score", 0.0)),
                    text=str(payload.get("text", "")),
                    payload=payload,
                    metadata=dict(payload.get("metadata", {})),
                )
            )
        return out


def _build_filter_clauses(filters: dict[str, Any]) -> list[dict[str, Any]]:
    clauses: list[dict[str, Any]] = []
    for key, expected in filters.items():
        if isinstance(expected, (list, tuple, set)):
            clauses.append({"terms": {key: list(expected)}})
        else:
            clauses.append({"term": {key: expected}})
    return clauses


__all__ = [
    "BM25Store",
    "BM25SearchResult",
    "FakeBM25Store",
    "OpenSearchBM25Store",
]
