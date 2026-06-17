"""Runtime agents — LangGraph orchestration (Phase 7, §13–§15).

The §13 ``LegalResearchState`` plus the §14 ``StateGraph`` wire the RAG pipeline into an
auditable agentic workflow. Each node is a framework-free ``state -> partial update``
function (testable bare); the graph in :mod:`packages.agents.graph` composes them with
the §14 routing rules and per-step traces.
"""

from packages.agents.graph import build_graph, run_graph
from packages.agents.state import (
    CitationAuditResult,
    LegalResearchState,
    RetrievedSource,
)

__all__ = [
    "build_graph",
    "run_graph",
    "LegalResearchState",
    "RetrievedSource",
    "CitationAuditResult",
]
