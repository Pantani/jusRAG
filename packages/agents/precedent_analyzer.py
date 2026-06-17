"""PrecedentAnalyzerAgent — precedent authority node (§15.5).

Tags the authority of each retrieved case-law source using the §15.5 taxonomy
(binding_precedent, repetitive_appeal, general_repercussion, binding_summary, summary,
ordinary_case_law, unknown). It reads only metadata already on the retrieved sources
(``precedent_type``/``is_binding``/``court``) — it never reclassifies a decision as a
binding thesis without evidence (§15.4). A coherent skeleton over the seed corpus:
súmulas map to ``summary``, binding ones to ``binding_summary``, and so on.

The classification is written back into each source's metadata so the risk checker can
warn when a non-binding decision is being relied on.
"""

from __future__ import annotations

from typing import Any

from packages.agents.state import LegalResearchState, RetrievedSource
from packages.legal_types.enums import PrecedentType

_BINDING_BY_TYPE: dict[str, PrecedentType] = {
    "binding_precedent": PrecedentType.BINDING_PRECEDENT,
    "repetitive_appeal": PrecedentType.REPETITIVE_APPEAL,
    "general_repercussion": PrecedentType.GENERAL_REPERCUSSION,
    "binding_summary": PrecedentType.BINDING_SUMMARY,
    "summary": PrecedentType.SUMMARY,
    "ordinary_case_law": PrecedentType.ORDINARY_CASE_LAW,
}


def classify_precedent(source: RetrievedSource) -> PrecedentType:
    """Derive the §15.5 authority class from the source's metadata."""

    raw = str(source.metadata.get("precedent_type", "")).lower()
    mapped = _BINDING_BY_TYPE.get(raw)
    if mapped is not None:
        if mapped is PrecedentType.SUMMARY and source.metadata.get("is_binding"):
            return PrecedentType.BINDING_SUMMARY
        return mapped
    return PrecedentType.UNKNOWN


def run_precedent_analysis(state: LegalResearchState) -> dict[str, Any]:
    """Graph node: annotate each case-law source with its precedent authority (§15.5)."""

    annotated: list[RetrievedSource] = []
    for source in state.retrieved_case_law:
        authority = classify_precedent(source)
        annotated.append(
            source.model_copy(
                update={"metadata": {**source.metadata, "precedent_authority": authority.value}}
            )
        )
    return {"retrieved_case_law": annotated}
