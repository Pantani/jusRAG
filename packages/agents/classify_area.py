"""LegalAreaClassifier — scope control node (§15.2).

The robust scope gate the earlier phases lacked. For the MVP it decides ``consumer``
vs everything-else and feeds the §14 routing: out-of-scope questions that also surface
no source must end in a safe refusal (§2.2, §2.3) — the classifier provides the
first half of that signal, retrieval provides the second.

Deterministic and offline (keyword evidence over the question). The taxonomy follows
§15.2; only ``consumer`` is covered by the seed corpus, so any other area is reported
honestly rather than answered beyond the base's competence (§15.2 MVP rule).
"""

from __future__ import annotations

from typing import Any

from packages.agents.state import LegalResearchState
from packages.legal_types.enums import LegalArea

# Evidence keywords per area. Consumer is the in-scope MVP area; the rest exist so the
# classifier can name the out-of-scope area honestly instead of forcing ``unknown``.
_AREA_KEYWORDS: dict[LegalArea, tuple[str, ...]] = {
    LegalArea.CONSUMER: (
        "consumidor",
        "fornecedor",
        "produto",
        "serviço",
        "servico",
        "compra",
        "defeito",
        "vício",
        "vicio",
        "garantia",
        "arrependimento",
        "cdc",
        "loja",
        "reembolso",
        "troca",
    ),
    LegalArea.TAX: ("imposto", "tributo", "tributár", "fiscal", "icms", "iss", "cripto"),
    LegalArea.LABOR: ("trabalh", "clt", "empregad", "salário", "salario", "demiss"),
    LegalArea.CRIMINAL: ("crime", "penal", "delito", "homicídio", "homicidio"),
    LegalArea.CONSTITUTIONAL: ("constituição", "constituicao", "constitucional"),
    LegalArea.ADMINISTRATIVE: ("licitação", "licitacao", "servidor público"),
    LegalArea.CIVIL: ("contrato civil", "posse", "usucapião", "usucapiao"),
}

# Area considered in scope for the seed corpus (§1 MVP).
IN_SCOPE_AREA = LegalArea.CONSUMER


def _score_area(question: str, keywords: tuple[str, ...]) -> int:
    return sum(1 for kw in keywords if kw in question)


def classify_area(question: str) -> LegalArea:
    """Classify the legal area by keyword evidence (§15.2)."""

    normalized = question.lower()
    scored = {
        area: _score_area(normalized, kws) for area, kws in _AREA_KEYWORDS.items()
    }
    best_area = max(scored, key=lambda area: scored[area])
    if scored[best_area] == 0:
        return LegalArea.UNKNOWN
    return best_area


def is_in_scope(area: LegalArea) -> bool:
    """Whether the seed corpus is expected to cover this area (§15.2 MVP)."""

    return area is IN_SCOPE_AREA


def run_classify_area(state: LegalResearchState) -> dict[str, Any]:
    """Graph node: set ``legal_area`` and out-of-scope caveat (§15.2)."""

    area = classify_area(state.question)
    update: dict[str, Any] = {"legal_area": area.value}
    if not is_in_scope(area):
        caveat = (
            "A base atual cobre principalmente Direito do Consumidor; "
            f"a pergunta parece ser de área '{area.value}'."
        )
        update["caveats"] = [*state.caveats, caveat]
    return update
