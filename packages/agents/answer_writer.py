"""AnswerWriterAgent — synthesize_answer node (§15.6).

Reuses the answer layer (``LLMProvider`` + ``build_context``/``build_answer``) — it does
not reimplement synthesis. From ``selected_context`` it rebuilds a ``BuiltContext``,
prompts the LLM for a grounded draft, and formats the structured ``AnswerResponse``
(short answer, statute-grounded ``legal_basis``, separated ``case_law``, §32 disclaimer).

Because §13 stores only ``RetrievedSource``/strings, the structured ``AnswerResponse``
is parked in a per-run :class:`AnswerBuffer` so the downstream audit/risk nodes operate
on the same object (the state carries the rendered ``draft_answer`` text). On the audit
retry route (§14) this node re-runs and overwrites the buffer; the conservative second
pass is enforced by the answer layer's own claim-dropping when re-synthesized.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from packages.agents._adapters import source_to_chunk
from packages.agents.state import LegalResearchState
from packages.agents.trace import RETRY_MARKER, retry_attempts
from packages.answer.formatter import build_answer
from packages.answer.prompts import build_answer_messages
from packages.answer.schemas import AnswerResponse, AnswerStatus
from packages.llm.base import LLMProvider
from packages.rag.context_builder import BuiltContext, build_context
from packages.rag.types import RetrievedChunk


@dataclass
class AnswerBuffer:
    """Per-run holder for the structured answer threaded between synthesize/audit/risk.

    Keeps the §13 state exactly normative (no extra fields) while letting the audit and
    risk nodes work on the structured ``AnswerResponse`` and its ``BuiltContext``.
    """

    answers: dict[str, AnswerResponse] = field(default_factory=dict)
    contexts: dict[str, BuiltContext] = field(default_factory=dict)

    def put(self, run_id: str, answer: AnswerResponse, context: BuiltContext) -> None:
        self.answers[run_id] = answer
        self.contexts[run_id] = context

    def answer(self, run_id: str) -> AnswerResponse | None:
        return self.answers.get(run_id)

    def context(self, run_id: str) -> BuiltContext:
        return self.contexts.get(run_id, BuiltContext(text="", citations=[], chunks=[]))


def render_answer_text(answer: AnswerResponse) -> str:
    """Flatten a structured answer into the §15.6 textual format."""

    lines = [answer.short_answer]
    if answer.legal_basis:
        lines.append("\nFundamento legal:")
        lines += [f"- {item.text}" for item in answer.legal_basis]
    if answer.case_law:
        lines.append("\nJurisprudência relevante:")
        lines += [f"- {c.title}: {c.ementa}" for c in answer.case_law]
    return "\n".join(lines)


def _make_conservative(answer: AnswerResponse, state: LegalResearchState) -> AnswerResponse:
    """On the retry pass, drop the claims the prior audit flagged as unsupported (§14)."""

    if state.audit is None:
        return answer
    unsupported = set(state.audit.unsupported_claims)
    if not unsupported:
        return answer
    kept = [item for item in answer.legal_basis if item.text not in unsupported]
    short = answer.short_answer
    if short in unsupported:
        short = kept[0].text if kept else short
    return answer.model_copy(update={"legal_basis": kept, "short_answer": short})


def make_answer_writer(
    llm: LLMProvider,
    buffer: AnswerBuffer,
) -> Callable[[LegalResearchState], dict[str, Any]]:
    """Build the ``synthesize_answer`` node bound to an LLM provider (§15.6)."""

    def run_synthesize_answer(state: LegalResearchState) -> dict[str, Any]:
        attempt = retry_attempts(state.errors)
        chunks: list[RetrievedChunk] = [source_to_chunk(s) for s in state.selected_context]
        context = build_context(chunks)
        case_law_chunks = [c for c in chunks if c.citation.doc_type == "case_law"]

        messages = build_answer_messages(state.question, context)
        draft = llm.generate_answer(messages, context)
        answer = build_answer(draft, context, case_law_chunks)
        if attempt >= 1:
            answer = _make_conservative(answer, state)
        buffer.put(state.run_id, answer, context)

        status = "refused" if answer.status is AnswerStatus.REFUSED else "running"
        return {"draft_answer": render_answer_text(answer), "status": status}

    return run_synthesize_answer


# Re-exported so the graph router can mark a synthesis retry uniformly.
__all__ = ["AnswerBuffer", "make_answer_writer", "render_answer_text", "RETRY_MARKER"]
