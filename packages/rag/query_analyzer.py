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

# Matches "art. 12", "artigo 49", "art 6º", "art. 1.238", "art 1240-A".
# The numeric stem allows internal thousands dots (``1.238``) but the capture
# stops before a trailing dot (sentence-final ".") because ``[\d.]*`` is greedy
# yet a lone non-digit-followed dot is shed by the ``.replace`` + the fact that
# the class only matches digits/dots — a final "." is captured then stripped to
# dotless, and the optional ordinal mark / ``-A`` letter suffix are preserved so
# the token converges to the chunker's dotless ``article`` field (§ chunker doc:
# "art. 1.238"/"art 1238" -> "1238"; "art. 6º" -> "6º"; "art 1240-A" -> "1240-A").
_ARTICLE_RE = re.compile(
    r"\bart(?:igo|\.)?\s*(\d[\d.]*[ºo°]?(?:-[A-Z])?)",
    re.IGNORECASE,
)


def extract_article(query: str) -> str | None:
    """Return the first article number referenced in the query, if any.

    Normalizes the captured number to the **dotless** token used by the chunker's
    ``article`` field and ``legal_ranker.exact_citation_match`` (thousands dots
    removed; ordinal mark / letter suffix preserved): ``art. 1.238`` -> ``1238``.
    """

    match = _ARTICLE_RE.search(query)
    if not match:
        return None
    return match.group(1).replace(".", "")


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
