"""Integration: ``make ask-demo`` showcase runs the agentic runtime (AD-1 fix).

The demo must mirror the product's runtime behaviour: an out-of-scope question
(imposto sobre cripto) ends in a safe refusal via the ``LegalAreaClassifier`` scope
gate, never falling back to an irrelevant consumer súmula; the in-scope consumer
questions keep answering with the right statute/jurisprudence grounding. Fully
offline through the fake providers (§2.8).
"""

from __future__ import annotations

from apps.worker.jobs.ask_demo import DemoRuntime
from packages.answer.schemas import AnswerResponse


def _basis_citations(answer: AnswerResponse) -> list[str]:
    return [c for item in answer.legal_basis for c in item.citations]


def test_out_of_scope_crypto_question_is_refused() -> None:
    runtime = DemoRuntime()

    state, answer = runtime.ask(
        "Qual a alíquota do imposto de renda sobre criptomoedas?", run_id="t-crypto"
    )

    assert state.status == "refused"
    # Nothing invented and no irrelevant consumer source cited.
    if answer is not None:
        assert answer.legal_basis == []
        assert answer.case_law == []


def test_in_scope_consumer_questions_stay_answered() -> None:
    runtime = DemoRuntime()

    state_defeito, ans_defeito = runtime.ask(
        "O fornecedor responde por defeito do produto?", run_id="t-defeito"
    )
    state_arrep, ans_arrep = runtime.ask(
        "O consumidor tem direito de arrependimento na compra online?",
        run_id="t-arrep",
    )
    state_banco, ans_banco = runtime.ask(
        "O CDC se aplica a banco e instituição financeira?", run_id="t-banco"
    )

    assert state_defeito.status == "answered"
    assert ans_defeito is not None
    assert "cdc-8078-1990-art-12" in _basis_citations(ans_defeito)

    assert state_arrep.status == "answered"
    assert ans_arrep is not None
    assert "cdc-8078-1990-art-49" in _basis_citations(ans_arrep)

    assert state_banco.status == "answered"
    assert ans_banco is not None
    assert any(c.title == "STJ Súmula 297" for c in ans_banco.case_law)
