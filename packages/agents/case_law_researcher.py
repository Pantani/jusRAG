"""CaseLawResearchAgent — jurisprudence retrieval node (§15.4).

Orchestrates :class:`SearchService` filtered to ``doc_type=case_law``, preserving
court/case-number/relator/date/URL in each :class:`RetrievedSource`'s metadata (§15.4).
Never fabricates: an empty result yields an empty ``retrieved_case_law`` and the answer
simply omits the jurisprudence block (§22). The precedent analyzer downstream tags the
binding authority; this node only retrieves.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from packages.agents._adapters import chunk_to_source
from packages.agents.state import LegalResearchState
from packages.legal_types.enums import DocType
from packages.rag.search_service import SearchService

_TOP_K = 8


def make_case_law_researcher(
    search: SearchService,
    *,
    top_k: int = _TOP_K,
) -> Callable[[LegalResearchState], dict[str, Any]]:
    """Build the ``retrieve_case_law`` node bound to a search service (§15.4)."""

    def run_case_law_research(state: LegalResearchState) -> dict[str, Any]:
        filters: dict[str, Any] = {"doc_type": DocType.CASE_LAW.value}
        if state.legal_area:
            filters["legal_area"] = state.legal_area
        chunks = search.search(state.question, top_k, filters)
        return {"retrieved_case_law": [chunk_to_source(c) for c in chunks]}

    return run_case_law_research
