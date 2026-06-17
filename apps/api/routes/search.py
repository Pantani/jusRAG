"""POST /search — retrieve ranked legal chunks for a query (§29).

No business logic here: the route validates the wire shape and delegates to the
``SearchService`` injected via dependencies. Response carries each chunk's score
and citation metadata.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from apps.api.dependencies import SearchServiceDep
from packages.rag.types import RetrievedChunk

router = APIRouter(tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=8, ge=1, le=50)
    filters: dict[str, Any] | None = None
    # When true, the response also carries statute/case_law as separate blocks
    # (§4/§22) so legislation and jurisprudence stay visibly separated.
    separate: bool = False


class CitationOut(BaseModel):
    title: str
    article: str | None
    source_url: str | None
    chunk_id: str
    doc_type: str
    source: str


class SearchHit(BaseModel):
    chunk_id: str
    text: str
    score: float
    semantic_score: float
    citation: CitationOut
    metadata: dict[str, Any]


class SeparatedHits(BaseModel):
    statutes: list[SearchHit]
    case_law: list[SearchHit]


class SearchResponse(BaseModel):
    query: str
    top_k: int
    results: list[SearchHit]
    # Present only when the request set ``separate=true``. ``case_law`` is empty
    # when no jurisprudence source was retrieved (never fabricated, §22).
    separated: SeparatedHits | None = None


def _to_hit(chunk: RetrievedChunk) -> SearchHit:
    return SearchHit(
        chunk_id=chunk.chunk_id,
        text=chunk.text,
        score=chunk.score,
        semantic_score=chunk.semantic_score,
        citation=CitationOut(
            title=chunk.citation.title,
            article=chunk.citation.article,
            source_url=chunk.citation.source_url,
            chunk_id=chunk.citation.chunk_id,
            doc_type=chunk.citation.doc_type,
            source=chunk.citation.source,
        ),
        metadata=chunk.metadata,
    )


@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest, service: SearchServiceDep) -> SearchResponse:
    if request.separate:
        return _separated_response(request, service)
    hits = service.search(request.query, request.top_k, request.filters)
    return SearchResponse(
        query=request.query,
        top_k=request.top_k,
        results=[_to_hit(h) for h in hits],
    )


def _separated_response(request: SearchRequest, service: SearchServiceDep) -> SearchResponse:
    blocks = service.search_separated(request.query, request.top_k, request.filters)
    statutes = [_to_hit(h) for h in blocks.statutes]
    case_law = [_to_hit(h) for h in blocks.case_law]
    return SearchResponse(
        query=request.query,
        top_k=request.top_k,
        results=statutes + case_law,
        separated=SeparatedHits(statutes=statutes, case_law=case_law),
    )
