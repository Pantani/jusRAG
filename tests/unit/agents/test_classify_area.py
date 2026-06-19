"""Unit: multi-area scope classifier (§15.2), fully offline and deterministic.

Covers correct classification of the six in-scope areas (consumer/CDC, civil/CC+CPC,
criminal/CP+CPP, labor/CLT, tax/CTN, constitutional/CF), the in-scope/out-of-scope split
(administrative has no corpus → out), discriminant tie-breaking between overlapping
vocabularies, and the safe-refusal contract: out-of-scope or sourceless questions never
get a fabricated area-as-answer; they flow to refusal via empty retrieval (§2.2/§2.3).
"""

from __future__ import annotations

import pytest

from packages.agents.classify_area import (
    IN_SCOPE_AREAS,
    classify_area,
    is_in_scope,
    matched_out_of_scope_regime,
    run_classify_area,
)
from packages.agents.state import LegalResearchState
from packages.legal_types.enums import LegalArea


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("o fornecedor responde por vício do produto comprado?", LegalArea.CONSUMER),
        ("posso pedir reembolso na loja por direito de arrependimento?", LegalArea.CONSUMER),
        ("usucapião extraordinária de imóvel e responsabilidade civil", LegalArea.CIVIL),
        ("petição inicial e recurso de execução por dano moral", LegalArea.CIVIL),
        ("divórcio, herança e partilha de condomínio", LegalArea.CIVIL),
        ("homicídio culposo e legítima defesa", LegalArea.CRIMINAL),
        ("inquérito policial, flagrante e habeas corpus", LegalArea.CRIMINAL),
        ("furto e estelionato configuram crime com dolo", LegalArea.CRIMINAL),
        ("rescisão do contrato de trabalho, FGTS e aviso prévio", LegalArea.LABOR),
        ("empregador deve pagar hora extra e férias ao empregado", LegalArea.LABOR),
        ("fato gerador do ICMS e crédito tributário", LegalArea.TAX),
        ("lançamento de imposto e obrigação tributária", LegalArea.TAX),
        ("mandado de segurança e direito fundamental", LegalArea.CONSTITUTIONAL),
        ("separação de poderes e competência da união", LegalArea.CONSTITUTIONAL),
    ],
)
def test_classify_in_scope_areas(question: str, expected: LegalArea) -> None:
    assert classify_area(question) is expected
    assert is_in_scope(expected)


def test_overlap_consumer_contract_vs_civil_contract() -> None:
    # "contrato" alone is civil-weighted, but consumer-discriminant terms win.
    assert classify_area("contrato de compra de produto com o fornecedor") is LegalArea.CONSUMER
    # Pure civil contract framing stays civil.
    assert classify_area("rescisão de contrato de locação e posse do imóvel") is LegalArea.CIVIL


def test_overlap_prescricao_is_ambiguous_resolved_by_discriminant() -> None:
    # Bare "prescrição" is civil-weighted; consumer wins only with consumer cues.
    assert classify_area("prazo de prescrição da pretensão") is LegalArea.CIVIL
    assert classify_area("prescrição da garantia do produto do fornecedor") is LegalArea.CONSUMER


def test_administrative_is_out_of_scope() -> None:
    assert classify_area("licitação e improbidade do servidor público") is LegalArea.ADMINISTRATIVE
    assert not is_in_scope(LegalArea.ADMINISTRATIVE)


def test_out_of_scope_regime_term_prevails_over_incidental_in_scope_keyword() -> None:
    # "contrato" is civil-weighted, but the administrative regime term must win (§2.2).
    assert classify_area("licitação e contratos administrativos") is LegalArea.ADMINISTRATIVE
    # "contribuição" no longer maps to tax; previdenciário regime → unknown (out of scope).
    assert classify_area("aposentadoria por tempo de contribuição") is LegalArea.UNKNOWN
    assert classify_area("quanto recolho de INSS na previdência") is LegalArea.UNKNOWN
    # Empresarial/societário regime → unknown, never constitutional/civil.
    assert classify_area("sociedade empresária limitada") is LegalArea.UNKNOWN
    assert classify_area("dissolução de sociedade anônima") is LegalArea.UNKNOWN


def test_inventario_is_civil_in_scope() -> None:
    # Sucessões (CC) / procedimento (CPC): inventory vocabulary maps to civil.
    assert classify_area("como se processa o inventário judicial de bens") is LegalArea.CIVIL
    assert classify_area("partilha do espólio na sucessão") is LegalArea.CIVIL
    assert is_in_scope(LegalArea.CIVIL)


@pytest.mark.parametrize(
    "question",
    [
        "registro de marca no INPI",
        "validade de uma patente de invenção",
        "licenciamento ambiental de uma usina",
        "propaganda eleitoral antecipada e candidatura",
        "extradição de estrangeiro foragido",
        "naturalização de estrangeiro residente",
        "responsabilidade no transporte marítimo de cargas",
        "recuperação judicial de empresa em crise",
    ],
)
def test_held_out_corpusless_regimes_are_out_of_scope(question: str) -> None:
    # New regimes without corpus must never leak into an in-scope area (§2.2).
    assert not is_in_scope(classify_area(question))


def test_generic_brand_term_does_not_leak_consumer_to_out_of_scope() -> None:
    # "marca" alone (a brand) must not trigger the propriedade-industrial OOS signal.
    assert classify_area("o consumidor pode trocar produto de outra marca") is LegalArea.CONSUMER


def test_substring_oos_term_does_not_false_positive_on_longer_word() -> None:
    # Regression (Codex BUG 1): "licitação" must NOT match inside "solicitação".
    # A legitimate consumer question stays consumer instead of being refused as
    # administrative before retrieval (§2.2 in reverse: never refuse what the corpus
    # covers).
    assert classify_area("solicitação de reembolso ao fornecedor") is LegalArea.CONSUMER
    assert is_in_scope(LegalArea.CONSUMER)
    # A genuine licitação question still resolves to administrative (out of scope).
    assert classify_area("licitação para contratação de servidor") is LegalArea.ADMINISTRATIVE
    assert not is_in_scope(LegalArea.ADMINISTRATIVE)


def test_contrato_de_trabalho_resolves_to_labor_not_civil() -> None:
    # Regression (Codex BUG 2): generic civil "contrato" must not steal a CLT query,
    # which would filter legal_area=civil and drop the CLT chunks.
    assert classify_area("contrato de trabalho") is LegalArea.LABOR
    assert classify_area("rescisão do contrato de trabalho") is LegalArea.LABOR
    assert is_in_scope(LegalArea.LABOR)
    # Legitimate civil contract framings stay civil — no regression on the civil side.
    assert classify_area("contrato de locação") is LegalArea.CIVIL
    assert classify_area("contrato e obrigação de indenização por dano moral") is LegalArea.CIVIL


def test_unknown_when_no_evidence() -> None:
    assert classify_area("qual o melhor restaurante da cidade?") is LegalArea.UNKNOWN
    assert not is_in_scope(LegalArea.UNKNOWN)


def test_in_scope_set_is_exactly_the_six_ingested_areas() -> None:
    assert IN_SCOPE_AREAS == frozenset(
        {
            LegalArea.CONSUMER,
            LegalArea.CIVIL,
            LegalArea.CRIMINAL,
            LegalArea.LABOR,
            LegalArea.TAX,
            LegalArea.CONSTITUTIONAL,
        }
    )


def test_out_of_scope_area_emits_caveat_but_never_an_answer() -> None:
    update = run_classify_area(
        LegalResearchState(run_id="r", question="regras de licitação para servidor público")
    )
    assert update["legal_area"] == LegalArea.ADMINISTRATIVE.value
    assert any("fora da cobertura" in c for c in update["caveats"])
    # The node only labels the area; it never sets a draft/final answer (§2.2).
    assert "draft_answer" not in update and "final_answer" not in update


def test_in_scope_area_has_no_caveat() -> None:
    for q in ("fato gerador do ICMS", "homicídio culposo", "FGTS e aviso prévio"):
        update = run_classify_area(LegalResearchState(run_id="r", question=q))
        assert "caveats" not in update


# ---------------------------------------------------------------------------
# matched_out_of_scope_regime: explicit OOS signal vs. no-evidence unknown (§2.2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "Como registrar marca no INPI?",
        "requisitos do licenciamento ambiental",
        "aposentadoria por tempo de contribuição",
        "regras de licitação para servidor público",
        "pedido de recuperação judicial da sociedade limitada",
        "registro de candidatura no processo eleitoral",
        "extradição de estrangeiro e naturalização",
        "transporte marítimo de cargas",
        "ação de improbidade contra agente público",
    ],
)
def test_matched_oos_regime_true_for_corpusless_terms(question: str) -> None:
    """A term proper to a corpus-less regime is a deterministic OOS hit (§2.2)."""

    assert matched_out_of_scope_regime(question) is True


@pytest.mark.parametrize(
    "question",
    [
        # In-corpus question whose keywords missed → unknown WITHOUT a regime hit:
        # it must proceed to retrieval, not pre-refuse.
        "Quais os ritos do procedimento de arrolamento de bens do falecido?",
        # In-scope questions never match a regime term.
        "vício do produto e direito de arrependimento",
        "fato gerador do ICMS",
        "homicídio culposo",
        "FGTS e aviso prévio",
        "usucapião extraordinária de imóvel",
    ],
)
def test_matched_oos_regime_false_when_no_regime_term(question: str) -> None:
    assert matched_out_of_scope_regime(question) is False


def test_no_evidence_unknown_is_not_an_oos_regime() -> None:
    """The enxuta inventário formulation lands on unknown but matches no regime."""

    q = "Quais os ritos do procedimento de arrolamento de bens do falecido?"
    assert classify_area(q) == LegalArea.UNKNOWN
    assert matched_out_of_scope_regime(q) is False


@pytest.mark.parametrize(
    "question",
    [
        # Held-out corpus-less regimes invented to confirm domain vocabulary, not
        # overfit to golden enunciados.
        "concurso público para o cargo de auditor",  # administrative
        "benefício previdenciário por incapacidade",  # previdenciário
        "ato administrativo e seus atributos de presunção",  # administrative
    ],
)
def test_matched_oos_regime_held_out(question: str) -> None:
    assert matched_out_of_scope_regime(question) is True
