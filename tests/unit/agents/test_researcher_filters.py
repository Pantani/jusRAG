"""Unit: researcher nodes apply the legal_area filter only when known (session-9 fix).

A known in-scope area must filter retrieval by ``legal_area`` so multi-area corpora stay
disjoint; ``unknown`` must NOT filter (else the §14 retrieval zeroes out and a real source
is lost). Refusal stays the job of the empty-selection §14 gate, not of the filter.
"""

from __future__ import annotations

from typing import Any

from packages.agents.case_law_researcher import make_case_law_researcher
from packages.agents.state import LegalResearchState
from packages.agents.statute_researcher import make_statute_researcher


class _SpySearch:
    """Captures the filters passed to ``search`` and returns no chunks."""

    def __init__(self) -> None:
        self.filters: dict[str, Any] | None = None

    def search(self, query: str, top_k: int, filters: dict[str, Any] | None) -> list[Any]:
        self.filters = filters
        return []


def test_statute_researcher_filters_by_known_area() -> None:
    spy = _SpySearch()
    node = make_statute_researcher(spy)  # type: ignore[arg-type]
    node(LegalResearchState(run_id="r", question="ICMS", legal_area="tax"))
    assert spy.filters is not None
    assert spy.filters.get("legal_area") == "tax"


def test_statute_researcher_skips_filter_when_unknown() -> None:
    spy = _SpySearch()
    node = make_statute_researcher(spy)  # type: ignore[arg-type]
    node(LegalResearchState(run_id="r", question="algo", legal_area="unknown"))
    assert spy.filters is not None
    assert "legal_area" not in spy.filters


def test_case_law_researcher_filters_by_known_area() -> None:
    spy = _SpySearch()
    node = make_case_law_researcher(spy)  # type: ignore[arg-type]
    node(LegalResearchState(run_id="r", question="furto", legal_area="criminal"))
    assert spy.filters is not None
    assert spy.filters.get("legal_area") == "criminal"


def test_case_law_researcher_skips_filter_when_unknown() -> None:
    spy = _SpySearch()
    node = make_case_law_researcher(spy)  # type: ignore[arg-type]
    node(LegalResearchState(run_id="r", question="algo", legal_area="unknown"))
    assert spy.filters is not None
    assert "legal_area" not in spy.filters
