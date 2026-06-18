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
    """Real OpenSearch BM25 adapter — stub.

    TODO(foundation): implement against the ``opensearch`` service in
    docker-compose. Until then, callers must use ``FakeBM25Store`` for offline
    testing; enabling hybrid against this class fails loudly rather than
    fabricating a lexical signal.
    """

    def index_chunks(self, chunks: list[LegalChunk]) -> None:
        raise NotImplementedError("OpenSearchBM25Store.index_chunks not implemented yet.")

    def search(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[BM25SearchResult]:
        raise NotImplementedError("OpenSearchBM25Store.search not implemented yet.")


__all__ = [
    "BM25Store",
    "BM25SearchResult",
    "FakeBM25Store",
    "OpenSearchBM25Store",
]
