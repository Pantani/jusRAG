"""RiskCheckerAgent — check_risks + final_answer node (§15.8, §34, §41).

The terminal node. It injects context-dependent caveats (depends on facts/proof,
out-of-scope coverage, missing jurisprudence) and the mandatory non-advice disclaimer
(§41), then renders the ``final_answer`` and sets the terminal ``status``.

Status resolution (§14): a buffered safe refusal becomes ``refused``; a graph already
routed to ``needs_more_info`` stays so (the question lacked critical facts); otherwise
the audited answer is finalized as ``answered``. The disclaimer is always present, so
no final answer can read as definitive legal advice (§2.6, §40).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from packages.agents.answer_writer import AnswerBuffer, render_answer_text
from packages.agents.state import LegalResearchState
from packages.answer.formatter import NON_ADVICE_DISCLAIMER, REFUSAL_SHORT_ANSWER
from packages.answer.schemas import AnswerResponse, AnswerStatus


def build_caveats(state: LegalResearchState, answer: AnswerResponse | None) -> list[str]:
    """Assemble caveats from state signals plus the mandatory disclaimer (§34/§41)."""

    caveats: list[str] = list(state.caveats)
    if state.missing_facts:
        caveats.append(
            "A conclusão depende de fatos adicionais: " + "; ".join(state.missing_facts)
        )
    if answer is not None and not answer.case_law:
        caveats.append(
            "Não foi recuperada jurisprudência aplicável; a análise se apoia na legislação."
        )
    caveats.append(
        "A conclusão pode depender de prova, documentos e datas do caso concreto."
    )
    if NON_ADVICE_DISCLAIMER not in caveats:
        caveats.append(NON_ADVICE_DISCLAIMER)
    return _dedupe(caveats)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _resolve_status(state: LegalResearchState, answer: AnswerResponse | None) -> str:
    if state.status == "needs_more_info":
        return "needs_more_info"
    if answer is None or answer.status is AnswerStatus.REFUSED:
        return "refused"
    return "answered"


def make_risk_checker(
    buffer: AnswerBuffer,
) -> Callable[[LegalResearchState], dict[str, Any]]:
    """Build the ``check_risks``/``final_answer`` node (§15.8)."""

    def run_check_risks(state: LegalResearchState) -> dict[str, Any]:
        answer = buffer.answer(state.run_id)
        status = _resolve_status(state, answer)
        caveats = build_caveats(state, answer)

        if status == "needs_more_info":
            final = (
                "Para pesquisar com segurança, preciso de mais contexto: "
                + "; ".join(state.missing_facts)
            )
        elif status == "refused" or answer is None:
            final = REFUSAL_SHORT_ANSWER
        else:
            final = render_answer_text(answer)

        return {"final_answer": final, "caveats": caveats, "status": status}

    return run_check_risks
