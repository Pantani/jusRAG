"""Query analysis: normalize the request and extract retrieval signals (§4).

MVP scope: trims the query, builds metadata filters from explicit ``legal_area``
/ ``doc_type``, and extracts any article number mentioned in the query (used by
the ranker's ``exact_citation_match`` term). No LLM call here — deterministic and
offline.
"""

from __future__ import annotations

import re

from packages.rag.types import RetrievalQuery
from packages.storage.payload import FILTERABLE_KEYS

# Matches "art. 12", "artigo 49", "art 6º" — captures the article number.
_ARTICLE_RE = re.compile(r"\bart(?:igo|\.)?\s*(\d+)", re.IGNORECASE)


def extract_article(query: str) -> str | None:
    """Return the first article number referenced in the query, if any."""

    match = _ARTICLE_RE.search(query)
    return match.group(1) if match else None


def build_filters(request: RetrievalQuery) -> dict[str, object]:
    """Merge explicit area/doc_type with any free-form filters (§9 keys only)."""

    filters: dict[str, object] = {}
    if request.legal_area:
        filters["legal_area"] = request.legal_area
    if request.doc_type:
        filters["doc_type"] = request.doc_type
    for key, value in request.filters.items():
        if key in FILTERABLE_KEYS and value is not None:
            filters[key] = value
    return filters
