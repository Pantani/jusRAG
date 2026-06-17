"""Adapters between the rag/answer shapes and the §13 runtime state.

The state stores :class:`RetrievedSource` (§13), while retrieval emits
:class:`RetrievedChunk` (§29) and synthesis consumes a :class:`BuiltContext`. These
pure converters keep the nodes free of duplicated mapping logic and ensure provenance
(``source_url``, ``doc_type``, score, citation metadata) survives the round-trip so the
auditor and risk checker see the same sources the retriever found.
"""

from __future__ import annotations

from packages.agents.state import RetrievedSource
from packages.rag.types import CitationRef, RetrievedChunk


def chunk_to_source(chunk: RetrievedChunk) -> RetrievedSource:
    """Map a retrieved chunk (§29) onto the state's ``RetrievedSource`` (§13)."""

    citation = chunk.citation
    return RetrievedSource(
        chunk_id=chunk.chunk_id,
        doc_type=citation.doc_type,
        title=citation.title,
        text=chunk.text,
        score=chunk.score,
        source_url=citation.source_url,
        metadata={
            "article": citation.article,
            "source": citation.source,
            "semantic_score": chunk.semantic_score,
            **chunk.metadata,
        },
    )


def source_to_chunk(source: RetrievedSource) -> RetrievedChunk:
    """Rebuild a ``RetrievedChunk`` from a state source for context/audit reuse."""

    meta = dict(source.metadata)
    semantic = float(meta.pop("semantic_score", source.score))
    article = meta.pop("article", None)
    src = meta.pop("source", "unknown")
    citation = CitationRef(
        title=source.title,
        article=article,
        source_url=source.source_url,
        chunk_id=source.chunk_id,
        doc_type=source.doc_type,
        source=src,
    )
    return RetrievedChunk(
        chunk_id=source.chunk_id,
        text=source.text,
        score=source.score,
        semantic_score=semantic,
        citation=citation,
        metadata=meta,
    )
