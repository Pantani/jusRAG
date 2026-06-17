"""Context builder: assemble retrieved chunks into an answer-ready context (§4).

Produces a deterministic, source-labeled context block plus the parallel list of
citations, keeping legislation text and its provenance paired. No LLM call here;
the answer writer (Phase 4) consumes this.
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.rag.types import CitationRef, RetrievedChunk


@dataclass(frozen=True)
class BuiltContext:
    """Context text plus the ordered citations it was built from."""

    text: str
    citations: list[CitationRef]
    chunks: list[RetrievedChunk]


def build_context(chunks: list[RetrievedChunk]) -> BuiltContext:
    """Render retrieved chunks into a labeled context block (order preserved)."""

    blocks: list[str] = []
    citations: list[CitationRef] = []
    for index, chunk in enumerate(chunks, start=1):
        label = _source_label(chunk.citation)
        blocks.append(f"[{index}] {label}\n{chunk.text}")
        citations.append(chunk.citation)
    return BuiltContext(text="\n\n".join(blocks), citations=citations, chunks=chunks)


def _source_label(citation: CitationRef) -> str:
    if citation.article:
        return f"{citation.title}, art. {citation.article}"
    return citation.title
