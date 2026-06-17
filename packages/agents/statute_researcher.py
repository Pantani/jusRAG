"""StatuteResearchAgent — legislation retrieval node (§15.3).

Orchestrates :class:`SearchService` (it does *not* reimplement retrieval) filtered to
``doc_type=statute`` and the classified ``legal_area``, preserving article/law/URL and
score in each :class:`RetrievedSource` (§15.3). Returns a node closure so the graph can
inject the service while the node stays a pure ``state -> partial update`` function.

Current legislation is favored implicitly via the seed corpus (``is_current`` chunks);
the score and citation metadata travel into the state for the ranker and auditor.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from packages.agents._adapters import chunk_to_source
from packages.agents.state import LegalResearchState
from packages.legal_types.enums import DocType
from packages.rag.search_service import SearchService

# Per-block retrieval depth; the rerank node trims the union to the working context.
_TOP_K = 8


def make_statute_researcher(
    search: SearchService,
    *,
    top_k: int = _TOP_K,
) -> Callable[[LegalResearchState], dict[str, Any]]:
    """Build the ``retrieve_statutes`` node bound to a search service (§15.3)."""

    def run_statute_research(state: LegalResearchState) -> dict[str, Any]:
        filters: dict[str, Any] = {"doc_type": DocType.STATUTE.value}
        if state.legal_area:
            filters["legal_area"] = state.legal_area
        chunks = search.search(state.question, top_k, filters)
        return {"retrieved_statutes": [chunk_to_source(c) for c in chunks]}

    return run_statute_research
