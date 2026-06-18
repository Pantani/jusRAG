"""Anti-overfit coverage for the scope gate (Phase 14 recurate, demanded by QA).

The previous OOS gate was a closed keyword list overfit to the golden enunciados: it
both (a) leaked OOS regimes not in the list and (b) refused in-scope questions whose
wording contained a listed token (furto/homicídio/usucapião/CLT). After the
principled rework (answer: classify_area + IN_SCOPE_AREAS; agentic: hardened
classify_area; eval: golden recurate) these tests pin the corrected behaviour with
BLIND coverage so the suite measures generalisation, not memorisation. As of the
Phase-14 eval-debt remediation, usucapião and guarda (CC Família/Sucessões) are
in-corpus after the CC ingestion fix and are pinned here as answered (no longer OOS):

* In-scope questions backed by real corpus are NOT refused — including the exact cases
  that the old keyword gate wrongly refused.
* The OOS refusal set spans a VARIETY of corpusless regimes, several of which the
  agentic classifier was NOT explicitly hardened on, so a regression to a closed list
  (memorising known OOS terms) would surface as a leak here rather than passing.

All offline: deterministic fakes, no network.
"""

from __future__ import annotations

import pytest

from packages.evals.golden import load_golden, out_of_scope_questions
from packages.evals.harness import build_harness

# In-scope questions with real corpus that the OLD keyword gate wrongly refused.
# Worded to anchor on the real article so the fake lexical retriever grounds them;
# every one MUST be answered (status != refused), never refused.
_IN_SCOPE_NOT_REFUSED = [
    # furto — was refused by the old "pena de reclusão" keyword (CP art. 155).
    pytest.param(
        "Furto subtrair para si ou para outrem coisa alheia móvel pena de reclusão?",
        id="furto-cp-155",
    ),
    # homicídio — same keyword collision (CP art. 121).
    pytest.param(
        "Homicídio matar alguém crime pena de reclusão de seis a vinte anos?",
        id="homicidio-cp-121",
    ),
    # latrocínio — migrated from OOS; CP art. 157 §3º is in corpus.
    pytest.param(
        "O roubo se da violência resultar morte latrocínio constitui crime subtrair "
        "coisa móvel alheia mediante grave ameaça ou violência a pessoa com pena de reclusão?",
        id="latrocinio-cp-157",
    ),
    # CLT justa causa — was refused by the old "clt" keyword (CLT art. 482).
    pytest.param(
        "Constituem justa causa para rescisão do contrato de trabalho pelo empregador "
        "a desídia no desempenho das funções e o abandono de emprego?",
        id="justa-causa-clt-482",
    ),
    # CLT insalubridade — migrated from OOS (CLT art. 192).
    pytest.param(
        "O exercício de trabalho em condições insalubres acima dos limites de "
        "tolerância estabelecidos assegura a percepção de adicional de insalubridade?",
        id="insalubridade-clt-192",
    ),
    # inventário judicial — migrated from OOS; CPC art. 610 is in corpus.
    pytest.param(
        "Havendo testamento ou interessado incapaz proceder-se-á ao inventário "
        "judicial e se todos forem capazes e concordes a partilha poderão ser feitas "
        "por escritura pública?",
        id="inventario-cpc-610",
    ),
    # usucapião — promoted from eval-real debt after the CC ingestion fix (CC art. 1.238).
    pytest.param(
        "Aquele que por quinze anos sem interrupção nem oposição possuir como seu um "
        "imóvel adquire-lhe a propriedade independentemente de título e boa-fé podendo "
        "requerer ao juiz que assim o declare por sentença?",
        id="usucapiao-cc-1238",
    ),
    # guarda compartilhada — promoted from eval-real debt after the CC fix (CC art. 1.583).
    pytest.param(
        "A guarda será unilateral ou compartilhada compreendendo-se por guarda "
        "compartilhada a responsabilização conjunta e o exercício de direitos e "
        "deveres do pai e da mãe que não vivam sob o mesmo teto?",
        id="guarda-cc-1583",
    ),
]

# Regimes the agentic classifier was NOT explicitly hardened on (held-out): they must
# refuse by ABSENCE of in-scope vocabulary, not by matching a memorised OOS term.
_HELD_OUT_OOS_IDS = {
    "oosx-amb-licenciamento",
    "oosx-amb-eia-rima",
    "oosx-pi-marca-inpi",
    "oosx-pi-patente-prazo",
    "oosx-mar-transporte",
    "oosx-conc-cade",
    "oosx-aut-direitos-autorais",
    "oosx-reg-civil-nascimento",
}


@pytest.mark.parametrize("question", _IN_SCOPE_NOT_REFUSED)
def test_in_scope_corpus_questions_are_not_refused(question: str) -> None:
    """In-scope questions with real corpus must be answered, never refused.

    These are exactly the cases the old keyword gate wrongly refused. The harness is
    the real pipeline over deterministic fakes; we assert the writer does not refuse.
    """

    answer = build_harness().answer_writer.write(question)
    assert answer.status.value != "refused", (
        f"in-scope question wrongly refused: {question!r}"
    )


def test_held_out_oos_regimes_are_present_for_generalisation() -> None:
    """The OOS golden must include held-out regimes (variety), not only memorised terms.

    Guards against a future regression that re-overfits the scope gate to the specific
    OOS enunciados the classifier already knows.
    """

    oos_ids = {q.id for q in out_of_scope_questions(load_golden())}
    missing = _HELD_OUT_OOS_IDS - oos_ids
    assert not missing, f"held-out OOS regimes dropped from the golden: {sorted(missing)}"


def test_held_out_oos_regimes_are_refused() -> None:
    """Every held-out OOS regime must be safely refused (§2.2), measuring generalisation."""

    harness = build_harness()
    held_out = [q for q in out_of_scope_questions(load_golden()) if q.id in _HELD_OUT_OOS_IDS]
    assert len(held_out) == len(_HELD_OUT_OOS_IDS)
    for q in held_out:
        answer = harness.answer_writer.write(q.question)
        assert answer.status.value == "refused", f"held-out OOS leaked: {q.id} {q.question!r}"
        assert answer.sources == [], f"refusal must carry no sources: {q.id}"


def test_oos_set_spans_multiple_distinct_regimes() -> None:
    """The OOS set must cover many distinct regimes (no single-regime overfit)."""

    oos = out_of_scope_questions(load_golden())
    # Distinct regime prefixes encoded in the ids (oosx-<regime>, oos-<regime>).
    regimes = {q.id.split("-")[1] for q in oos if "-" in q.id}
    assert len(regimes) >= 8, f"OOS regime variety too low ({len(regimes)}): {sorted(regimes)}"
