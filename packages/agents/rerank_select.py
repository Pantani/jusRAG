"""rerank_and_select_context node (§14).

Selects the working context from the two retrieved blocks. Retrieval already applied
the composite legal ranking (§38) inside the retriever, so this node's job is scope
filtering and selection, not re-scoring: it drops sources below the grounding semantic
threshold (the §2.2 first-pass gate reused from the answer layer) and unions statutes
(first) with case law into ``selected_context``. Legislation leads so the synthesized
``legal_basis`` is statute-grounded (§2.3).

Empty selection is the retrieval half of the §14 out-of-scope refusal signal.
"""

from __future__ import annotations

from typing import Any

from packages.agents.state import LegalResearchState, RetrievedSource

# First-pass semantic grounding threshold, mirrored from the answer layer so the graph
# and the non-agentic path agree on what counts as on-topic for the fake embedder.
_MIN_SEMANTIC_SCORE = 0.20
_MAX_CONTEXT = 8


def _grounded(sources: list[RetrievedSource], min_score: float) -> list[RetrievedSource]:
    return [
        s
        for s in sources
        if float(s.metadata.get("semantic_score", s.score)) >= min_score
    ]


def select_context(
    statutes: list[RetrievedSource],
    case_law: list[RetrievedSource],
    *,
    min_score: float = _MIN_SEMANTIC_SCORE,
    max_context: int = _MAX_CONTEXT,
) -> list[RetrievedSource]:
    """Union grounded statutes (first) and case law, truncated (§14)."""

    selected = _grounded(statutes, min_score) + _grounded(case_law, min_score)
    return selected[:max_context]


def run_rerank_and_select_context(state: LegalResearchState) -> dict[str, Any]:
    """Graph node: build ``selected_context`` from the retrieved blocks (§14)."""

    selected = select_context(state.retrieved_statutes, state.retrieved_case_law)
    return {"selected_context": selected}
