"""LangGraph runtime orchestration (§14).

Compiles the §14 flow into a LangGraph ``StateGraph`` over the §13
``LegalResearchState``:

    START → intake → classify_legal_area → retrieve_statutes → retrieve_case_law
          → analyze_precedents → rerank_and_select_context → synthesize_answer
          → audit_citations → check_risks → final_answer (check_risks) → END

Routing rules (§14), each a small conditional edge:
  (1) out of scope *and* no source → refusal (skip synthesis, finalize as ``refused``);
  (2) critical ``missing_facts`` → ``needs_more_info`` (skip synthesis, ask for context);
  (3) audit fails on the first pass → back to ``synthesize_answer`` once;
  (4) audit fails twice → conservative pass already applied, otherwise refuse.

Dependencies (search service, LLM, answer buffer, trace collector) are injected into the
node factories, so the same graph runs offline with fakes. Each node is wrapped with a
trace hook that records an auditable step (§3, §23). The state stays exactly §13.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph._node import StateNode

from packages.agents.answer_writer import AnswerBuffer, make_answer_writer
from packages.agents.case_law_researcher import make_case_law_researcher
from packages.agents.citation_auditor import make_citation_auditor
from packages.agents.classify_area import run_classify_area
from packages.agents.intake import run_intake
from packages.agents.precedent_analyzer import run_precedent_analysis
from packages.agents.rerank_select import run_rerank_and_select_context
from packages.agents.risk_checker import make_risk_checker
from packages.agents.state import LegalResearchState
from packages.agents.statute_researcher import make_statute_researcher
from packages.agents.trace import RETRY_MARKER, TraceCollector, retry_attempts
from packages.llm.base import LLMProvider
from packages.rag.search_service import SearchService

_MAX_SYNTHESIS_RETRIES = 1


def _traced(
    name: str,
    fn: Callable[[LegalResearchState], dict[str, Any]],
    collector: TraceCollector,
) -> StateNode[LegalResearchState, Any]:
    """Wrap a node so each execution records an auditable trace step (§3, §23)."""

    def wrapped(state: LegalResearchState) -> dict[str, Any]:
        update = fn(state)
        status = str(update.get("status", state.status))
        collector.record(state.run_id, name, status, _note(name, update))
        return update

    return wrapped


def _note(name: str, update: dict[str, Any]) -> str:
    if name == "classify_legal_area":
        return f"legal_area={update.get('legal_area')}"
    if name in ("retrieve_statutes", "retrieve_case_law"):
        key = "retrieved_statutes" if name == "retrieve_statutes" else "retrieved_case_law"
        return f"{key}={len(update.get(key, []))}"
    if name == "rerank_and_select_context":
        return f"selected_context={len(update.get('selected_context', []))}"
    if name == "audit_citations":
        audit = update.get("audit")
        return f"passed={getattr(audit, 'passed', None)}"
    return ""


# --- routers ------------------------------------------------------------------


def _route_after_intake(state: LegalResearchState) -> str:
    """(2) Critical missing facts → needs_more_info; else proceed to classify."""

    if state.missing_facts:
        return "needs_more_info"
    return "classify_legal_area"


def _route_after_select(state: LegalResearchState) -> str:
    """(1) No source in scope (esp. out-of-scope) → refusal; else synthesize."""

    if not state.selected_context:
        return "refusal"
    return "synthesize_answer"


def _route_after_audit(state: LegalResearchState) -> str:
    """(3)/(4) Audit pass → finalize; first failure → retry; second → finalize."""

    if state.audit is not None and state.audit.passed:
        return "check_risks"
    if retry_attempts(state.errors) < _MAX_SYNTHESIS_RETRIES:
        return "retry_synthesis"
    return "check_risks"


def _mark_needs_more_info(state: LegalResearchState) -> dict[str, Any]:
    return {"status": "needs_more_info"}


def _mark_retry(state: LegalResearchState) -> dict[str, Any]:
    """Record a synthesis re-attempt (counted by the router) without touching §13 shape."""

    return {"errors": [*state.errors, RETRY_MARKER]}


def build_graph(
    *,
    search: SearchService,
    llm: LLMProvider,
    buffer: AnswerBuffer | None = None,
    collector: TraceCollector | None = None,
) -> Any:
    """Compile the §14 LangGraph. Returns the compiled app and the trace collector."""

    buffer = buffer or AnswerBuffer()
    collector = collector or TraceCollector()

    g: StateGraph[LegalResearchState, Any, LegalResearchState, LegalResearchState] = (
        StateGraph(LegalResearchState)
    )
    g.add_node("intake", _traced("intake", run_intake, collector))
    g.add_node(
        "classify_legal_area",
        _traced("classify_legal_area", run_classify_area, collector),
    )
    g.add_node(
        "retrieve_statutes",
        _traced("retrieve_statutes", make_statute_researcher(search), collector),
    )
    g.add_node(
        "retrieve_case_law",
        _traced("retrieve_case_law", make_case_law_researcher(search), collector),
    )
    g.add_node(
        "analyze_precedents",
        _traced("analyze_precedents", run_precedent_analysis, collector),
    )
    g.add_node(
        "rerank_and_select_context",
        _traced("rerank_and_select_context", run_rerank_and_select_context, collector),
    )
    g.add_node(
        "synthesize_answer",
        _traced("synthesize_answer", make_answer_writer(llm, buffer), collector),
    )
    g.add_node(
        "audit_citations",
        _traced("audit_citations", make_citation_auditor(buffer), collector),
    )
    g.add_node("retry_synthesis", _traced("retry_synthesis", _mark_retry, collector))
    g.add_node(
        "needs_more_info",
        _traced("needs_more_info", _mark_needs_more_info, collector),
    )
    g.add_node("check_risks", _traced("check_risks", make_risk_checker(buffer), collector))

    g.add_edge(START, "intake")
    g.add_conditional_edges(
        "intake",
        _route_after_intake,
        {"needs_more_info": "needs_more_info", "classify_legal_area": "classify_legal_area"},
    )
    g.add_edge("needs_more_info", "check_risks")
    g.add_edge("classify_legal_area", "retrieve_statutes")
    g.add_edge("retrieve_statutes", "retrieve_case_law")
    g.add_edge("retrieve_case_law", "analyze_precedents")
    g.add_edge("analyze_precedents", "rerank_and_select_context")
    g.add_conditional_edges(
        "rerank_and_select_context",
        _route_after_select,
        {"refusal": "check_risks", "synthesize_answer": "synthesize_answer"},
    )
    g.add_edge("synthesize_answer", "audit_citations")
    g.add_conditional_edges(
        "audit_citations",
        _route_after_audit,
        {"check_risks": "check_risks", "retry_synthesis": "retry_synthesis"},
    )
    g.add_edge("retry_synthesis", "synthesize_answer")
    g.add_edge("check_risks", END)

    return g.compile()


def run_graph(
    question: str,
    *,
    run_id: str,
    search: SearchService,
    llm: LLMProvider,
    jurisdiction: str = "BR",
    collector: TraceCollector | None = None,
) -> LegalResearchState:
    """Convenience: build, invoke, and rehydrate the §13 state from the run."""

    collector = collector or TraceCollector()
    app = build_graph(search=search, llm=llm, collector=collector)
    initial = LegalResearchState(run_id=run_id, question=question, jurisdiction=jurisdiction)
    result = app.invoke(initial)
    return LegalResearchState.model_validate(result)
