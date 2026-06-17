"""Retriever I/O shapes (§29).

``RetrievalQuery`` is the retriever input; ``RetrievedChunk`` is its output —
the contract consumed by the answer/agentic layers and serialized by ``/search``.
Kept free of FastAPI/LLM coupling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RetrievalQuery:
    """Normalized retrieval request (§29)."""

    query: str
    top_k: int = 8
    legal_area: str | None = None
    doc_type: str | None = None
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CitationRef:
    """Minimal citation metadata for a retrieved chunk (§29)."""

    title: str
    article: str | None
    source_url: str | None
    chunk_id: str
    doc_type: str
    source: str


@dataclass(frozen=True)
class RetrievedChunk:
    """A ranked retrieval hit (§29).

    ``score`` is the final composite legal-ranking score; ``semantic_score`` keeps
    the raw vector similarity for transparency/debugging.
    """

    chunk_id: str
    text: str
    score: float
    semantic_score: float
    citation: CitationRef
    metadata: dict[str, Any] = field(default_factory=dict)
