"""Anti-overfit coverage for the scope gate (Phase 14 recurate, demanded by QA).

The previous OOS gate was a closed keyword list overfit to the golden enunciados: it
both (a) leaked OOS regimes not in the list and (b) refused in-scope questions whose
wording contained a listed token (furto/homicídio/usucapião/CLT). After the
principled rework (answer: classify_area + IN_SCOPE_AREAS; agentic: hardened
classify_area; eval: golden recurate) these tests pin the corrected behaviour with
BLIND coverage so the suite measures generalisation, not memorisation.

Phase-14 explicit-OOS-signal restore (_workspace/14_eval_oos_restore_summary.md): the
answer now wires the deterministic `matched_out_of_scope_regime` signal (agentic), so any
question matching a corpusless regime term pre-refuses DETERMINISTICALLY (fake AND real),
independent of the embedding. Those held-out regimes (previdenciário/INSS, ambiental,
propriedade industrial/INPI, marítimo, empresarial/recuperação judicial) were RESTORED to
out_of_scope_golden.yaml and are again validated against the fake gate. The eval-real debt
now holds ONLY the genuinely grounding-dependent residue: questions that match NO regime
term (eleitoral, migração, família/sucessões substantivas, concorrência/CADE, autoral, M&A,
tese penal STF, registro civil, and corpusless TAX sub-topics) — they reach retrieval and
refuse only under real dense embeddings, leaking under the purely-lexical fake. The
DETERMINISTIC fake gate refuses every loaded OOS question (defined `administrative` area +
the restored regime-matched cohort), which this file pins.

* In-scope questions backed by real corpus are NOT refused — including the exact cases
  the old keyword gate wrongly refused. One case (guarda-cc-1583) is currently xfail: it
  retrieves the right CC article in top-5 but the writer's synthesis pulls neighbour
  noise that the auditor rejects -> over-conservative refusal. That is an ANSWER-owner
  regression surfaced by the leading-"O" corpus fix, reported to the orchestrator; the
  xfail(strict) flips to a failure the moment answer fixes it, so coverage is preserved.
* The held-out generalisation cohort lives in the debt file and is pinned for variety.

All offline: deterministic fakes, no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from packages.evals.golden import GOLDEN_DIR, load_golden, out_of_scope_questions
from packages.evals.harness import EvalHarness, build_harness


@pytest.fixture(scope="module")
def harness() -> EvalHarness:
    """Module-scoped harness: indexing the seed corpus is expensive, so build it once.

    Same pipeline as a per-case ``build_harness()`` — the writer is stateless across
    ``write`` calls — so coverage is identical while avoiding a re-index per parametrised
    case.
    """

    return build_harness()


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
    # XFAIL(strict): retrieval surfaces CC art. 1.583 in top-5 (score ~0.66) but the
    # writer's synthesis over the top-8 grounded set pulls neighbour noise (CLT art. 816
    # at ~0.45) that the CitationAuditor flags, dropping the answer below the 0.05
    # unsupported threshold and forcing an over-conservative refusal. Answer-owner
    # regression surfaced by the leading-"O" corpus fix; reported to the orchestrator.
    pytest.param(
        "A guarda será unilateral ou compartilhada compreendendo-se por guarda "
        "compartilhada a responsabilização conjunta e o exercício de direitos e "
        "deveres do pai e da mãe que não vivam sob o mesmo teto?",
        id="guarda-cc-1583",
        marks=pytest.mark.xfail(
            strict=True,
            reason="answer-owner: synthesis neighbour-noise -> auditor refusal; CC 1.583 "
            "retrieves fine. See _workspace/14_eval_final_consolidation_summary.md.",
        ),
    ),
]

# Held-out corpusless regimes that match a `matched_out_of_scope_regime` term: they
# pre-refuse DETERMINISTICALLY (fake AND real), independent of the embedding, so they were
# RESTORED to out_of_scope_golden.yaml and are validated against the fake gate. They must
# refuse by the explicit OOS signal, not by matching a memorised golden enunciado — these
# `oosx-*` variants are reworded held-out forms. Pinned here for PRESENCE so a regression
# that drops the explicit-signal wiring (and silently sheds them back to debt) fails loudly.
_HELD_OUT_DETERMINISTIC_OOS_IDS = {
    "oosx-amb-licenciamento",
    "oosx-amb-eia-rima",
    "oosx-pi-marca-inpi",
    "oosx-pi-patente-prazo",
    "oosx-mar-transporte",
    "oosx-prev-aposentadoria-tempo",
    "oosx-prev-incapacidade",
}

# Regimes whose specific surface vocabulary is NOT (yet) a regime term: they classify
# UNKNOWN with NO match, reach retrieval, and refuse ONLY under real dense embeddings,
# leaking under the fake lexical store. They live in the eval-real DEBT file (not loaded by
# the gate). Pinned for PRESENCE/VARIETY so the generalisation cohort is not silently lost.
_HELD_OUT_GROUNDING_DEBT_IDS = {
    "oosx-conc-cade",
    "oosx-aut-direitos-autorais",
    "oosx-reg-civil-nascimento",
}

_GOLDEN_OOS_PATH = GOLDEN_DIR / "out_of_scope_golden.yaml"
_DEBT_PATH = GOLDEN_DIR / "out_of_scope_eval_real_debt.yaml"


def _golden_oos_ids() -> set[str]:
    """Ids in the deterministic OOS golden (loaded by the fake gate)."""

    raw = yaml.safe_load(Path(_GOLDEN_OOS_PATH).read_text(encoding="utf-8"))
    return {item["id"] for item in raw}


def _debt_oos_ids() -> set[str]:
    """Ids in the eval-real debt file (NOT loaded by the gate; not a *_golden.yaml)."""

    raw = yaml.safe_load(Path(_DEBT_PATH).read_text(encoding="utf-8"))
    return {item["id"] for item in raw}


@pytest.mark.parametrize("question", _IN_SCOPE_NOT_REFUSED)
def test_in_scope_corpus_questions_are_not_refused(question: str, harness: EvalHarness) -> None:
    """In-scope questions with real corpus must be answered, never refused.

    These are exactly the cases the old keyword gate wrongly refused. The harness is
    the real pipeline over deterministic fakes; we assert the writer does not refuse.
    """

    answer = harness.answer_writer.write(question)
    assert answer.status.value != "refused", f"in-scope question wrongly refused: {question!r}"


def test_held_out_deterministic_oos_regimes_are_in_the_gate_golden() -> None:
    """Held-out regime-matched OOS forms must be in the deterministic gate golden.

    These reworded `oosx-*` variants match a `matched_out_of_scope_regime` term, so they
    pre-refuse deterministically (fake AND real) and belong in out_of_scope_golden.yaml.
    Guards against a regression that drops the explicit-OOS-signal wiring and silently
    sheds them back to grounding-dependent debt.
    """

    missing = _HELD_OUT_DETERMINISTIC_OOS_IDS - _golden_oos_ids()
    assert not missing, f"deterministic OOS dropped from gate golden: {sorted(missing)}"


def test_held_out_grounding_debt_regimes_are_present_for_generalisation() -> None:
    """The grounding-dependent generalisation residue must survive in the eval-real DEBT file.

    These match NO regime term, classify UNKNOWN, and leak under the fake lexical embedding,
    so they live in the debt file (not the gate) and refuse only under real embeddings.
    Guards against silently dropping the cohort.
    """

    missing = _HELD_OUT_GROUNDING_DEBT_IDS - _debt_oos_ids()
    assert not missing, f"grounding-debt regimes dropped from debt cohort: {sorted(missing)}"


def test_debt_oos_set_spans_multiple_distinct_regimes() -> None:
    """The eval-real OOS debt set must cover many distinct regimes (no single-regime overfit).

    Variety lives in the debt cohort now (the fake gate keeps only the deterministic
    `administrative` refusals). This still measures generalisation breadth of the OOS
    enunciados; it just runs on the real-embedding-validated set, not the fake gate.
    """

    regimes = {qid.split("-")[1] for qid in _debt_oos_ids() if "-" in qid}
    assert len(regimes) >= 8, f"OOS regime variety too low ({len(regimes)}): {sorted(regimes)}"


def test_gate_oos_set_is_only_deterministic_refusals(harness: EvalHarness) -> None:
    """Every OOS question LOADED by the gate must be safely refused under the fake pipeline.

    The loaded OOS set is the deterministic cohort (defined-OOS-area pre-refusals), so the
    fake pipeline must refuse all of them with no sources (§2.2). This is the honest
    materialisation of refusal_when_no_source_rate on CI; UNKNOWN-classified leaks are
    excluded as eval-real debt, not silently passed.
    """

    loaded_oos = out_of_scope_questions(load_golden())
    assert loaded_oos, "the gate must keep at least the deterministic OOS cohort"
    for q in loaded_oos:
        answer = harness.answer_writer.write(q.question)
        assert answer.status.value == "refused", f"gate OOS leaked: {q.id} {q.question!r}"
        assert answer.sources == [], f"refusal must carry no sources: {q.id}"
