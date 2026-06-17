"""Search service: thin application service over the retriever.

Sits between the FastAPI route and the retriever so the route stays free of
business logic (system rule §5). Converts the wire request into a
``RetrievalQuery`` and the ``RetrievedChunk`` list into serializable dicts
matching the §29 retriever output.
"""

from __future__ import annotations

from typing import Any

from packages.rag.retriever import LegalRetriever, SeparatedRetrieval
from packages.rag.types import RetrievalQuery, RetrievedChunk


class SearchService:
    """Coordinates retrieval for the ``/search`` endpoint."""

    def __init__(self, retriever: LegalRetriever) -> None:
        self._retriever = retriever

    def search(
        self,
        query: str,
        top_k: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        return self._retriever.retrieve(self._build_query(query, top_k, filters))

    def search_separated(
        self,
        query: str,
        top_k: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> SeparatedRetrieval:
        """Retrieve statutes and case_law as separate blocks (§4/§22)."""

        return self._retriever.retrieve_separated(self._build_query(query, top_k, filters))

    @staticmethod
    def _build_query(
        query: str, top_k: int, filters: dict[str, Any] | None
    ) -> RetrievalQuery:
        return RetrievalQuery(
            query=query,
            top_k=top_k,
            legal_area=(filters or {}).get("legal_area"),
            doc_type=(filters or {}).get("doc_type"),
            filters=filters or {},
        )
