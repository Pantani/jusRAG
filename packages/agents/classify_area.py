"""LegalAreaClassifier — scope control node (§15.2).

The robust scope gate the earlier phases lacked. It picks a ``LegalArea`` from keyword
evidence over the question and feeds the §14 routing: out-of-scope questions that also
surface no source must end in a safe refusal (§2.2, §2.3) — the classifier provides the
first half of that signal, retrieval provides the second.

Deterministic and offline (weighted keyword evidence). The taxonomy follows §15.2. The
seed corpus now covers seven federal codes spanning six areas (consumer/CDC, civil/CC+CPC,
criminal/CP+CPP, labor/CLT, tax/CTN, constitutional/CF), so those areas are in scope and
their statute/case-law retrieval is filtered by ``legal_area``. ``administrative`` has no
ingested corpus and stays out of scope: when its retrieval comes back empty the §14 gate
refuses safely rather than inventing a source. Misclassification to ``unknown`` is benign:
the researchers then skip the ``legal_area`` filter (session-9 fix) instead of zeroing the
retrieval, so a real source can still surface.
"""

from __future__ import annotations

from typing import Any

from packages.agents.state import LegalResearchState
from packages.legal_types.enums import LegalArea

# Weighted evidence keywords per area. Highly discriminant terms (proper to a single
# code/area) score 2; ambiguous shared terms score 1 so they only break otherwise-equal
# ties. Substrings are matched, so stems like "tributár" cover declensions offline.
_AREA_KEYWORDS: dict[LegalArea, dict[str, int]] = {
    LegalArea.CONSUMER: {
        "consumidor": 2,
        "fornecedor": 2,
        "cdc": 2,
        "vício do produto": 2,
        "vicio do produto": 2,
        "direito de arrependimento": 2,
        "arrependimento": 1,
        "produto": 1,
        "serviço": 1,
        "servico": 1,
        "compra": 1,
        "defeito": 1,
        "vício": 1,
        "vicio": 1,
        "garantia": 1,
        "recall": 1,
        "loja": 1,
        "reembolso": 1,
        "troca": 1,
        "banco": 1,
        "instituição financeira": 2,
        "instituicao financeira": 2,
        "conta corrente": 2,
        "cartão": 1,
        "cartao": 1,
        "fraude": 1,
    },
    LegalArea.CIVIL: {
        "usucapião": 2,
        "usucapiao": 2,
        "responsabilidade civil": 2,
        "dano moral": 2,
        "herança": 2,
        "heranca": 2,
        "casamento": 2,
        "divórcio": 2,
        "divorcio": 2,
        "condomínio": 2,
        "condominio": 2,
        "locação": 2,
        "locacao": 2,
        "petição inicial": 2,
        "peticao inicial": 2,
        "tutela": 2,
        "posse": 2,
        "inventário": 2,
        "inventario": 2,
        "partilha": 2,
        "espólio": 2,
        "espolio": 2,
        "sucessão": 2,
        "sucessao": 2,
        "propriedade": 1,
        "contrato": 1,
        "obrigação": 1,
        "obrigacao": 1,
        "prescrição": 1,
        "prescricao": 1,
        "indenização": 1,
        "indenizacao": 1,
        "recurso": 1,
        "citação": 1,
        "citacao": 1,
        "sentença": 1,
        "sentenca": 1,
        "execução": 1,
        "execucao": 1,
    },
    LegalArea.CRIMINAL: {
        "homicídio": 2,
        "homicidio": 2,
        "furto": 2,
        "roubo": 2,
        "estelionato": 2,
        "legítima defesa": 2,
        "legitima defesa": 2,
        "inquérito": 2,
        "inquerito": 2,
        "habeas corpus": 2,
        "flagrante": 2,
        "denúncia": 2,
        "denuncia": 2,
        "dolo": 2,
        "culpa": 1,
        "crime": 1,
        "pena": 1,
        "penal": 1,
        "delito": 1,
        "prisão": 1,
        "prisao": 1,
    },
    LegalArea.LABOR: {
        "clt": 2,
        "empregad": 2,
        "empregador": 2,
        "trabalhador": 2,
        "fgts": 2,
        "hora extra": 2,
        "aviso prévio": 2,
        "aviso previo": 2,
        "rescisão": 2,
        "rescisao": 2,
        "jornada": 2,
        "férias": 1,
        "ferias": 1,
        "salário": 1,
        "salario": 1,
        "demiss": 1,
        "trabalh": 1,
    },
    LegalArea.TAX: {
        "icms": 2,
        "iss": 2,
        "ipi": 2,
        "fato gerador": 2,
        "crédito tributário": 2,
        "credito tributario": 2,
        "obrigação tributária": 2,
        "obrigacao tributaria": 2,
        "lançamento": 2,
        "lancamento": 2,
        "tributár": 2,
        "tributo": 2,
        "imposto": 1,
        "taxa": 1,
        "fiscal": 1,
        "cripto": 1,
    },
    LegalArea.CONSTITUTIONAL: {
        "direito fundamental": 2,
        "garantia constitucional": 2,
        "mandado de segurança": 2,
        "mandado de seguranca": 2,
        "devido processo": 2,
        "separação de poderes": 2,
        "separacao de poderes": 2,
        "competência da união": 2,
        "competencia da uniao": 2,
        "constitucional": 1,
        "constituição": 1,
        "constituicao": 1,
    },
}

# Terms proper to legal regimes that have NO ingested corpus. A regime-specific term here
# is a strong out-of-scope signal and must PREVAIL over incidental in-scope keywords (e.g.
# "licitação ... contratos": the administrative term wins over the civil "contrato"). The
# value is the area the term resolves to: ``administrative`` is in the enum; every other
# corpus-less regime (previdenciário, empresarial, propriedade industrial, ambiental,
# eleitoral, internacional, marítimo) collapses to ``unknown`` so the §14 gate refuses
# safely (§2.2). These terms are domain-discriminant, not golden enunciados.
_OUT_OF_SCOPE_TERMS: dict[str, LegalArea] = {
    # Administrative (enum value administrative)
    "licitação": LegalArea.ADMINISTRATIVE,
    "licitacao": LegalArea.ADMINISTRATIVE,
    "servidor público": LegalArea.ADMINISTRATIVE,
    "servidor publico": LegalArea.ADMINISTRATIVE,
    "concurso público": LegalArea.ADMINISTRATIVE,
    "concurso publico": LegalArea.ADMINISTRATIVE,
    "improbidade": LegalArea.ADMINISTRATIVE,
    "ato administrativo": LegalArea.ADMINISTRATIVE,
    # Previdenciário (no corpus → unknown)
    "previdência": LegalArea.UNKNOWN,
    "previdencia": LegalArea.UNKNOWN,
    "previdenciár": LegalArea.UNKNOWN,
    "inss": LegalArea.UNKNOWN,
    "aposentadoria": LegalArea.UNKNOWN,
    "benefício previdenciário": LegalArea.UNKNOWN,
    "beneficio previdenciario": LegalArea.UNKNOWN,
    # Empresarial / societário (no corpus → unknown)
    "sociedade empresária": LegalArea.UNKNOWN,
    "sociedade empresaria": LegalArea.UNKNOWN,
    "sociedade limitada": LegalArea.UNKNOWN,
    "sociedade anônima": LegalArea.UNKNOWN,
    "sociedade anonima": LegalArea.UNKNOWN,
    "falência": LegalArea.UNKNOWN,
    "falencia": LegalArea.UNKNOWN,
    "recuperação judicial": LegalArea.UNKNOWN,
    "recuperacao judicial": LegalArea.UNKNOWN,
    # Propriedade industrial (no corpus → unknown). "marca"/"patente" alone are too
    # generic (a consumer question may mention a brand), so we require discriminant forms.
    "registro de marca": LegalArea.UNKNOWN,
    "marca registrada": LegalArea.UNKNOWN,
    "patente de invenção": LegalArea.UNKNOWN,
    "patente de invencao": LegalArea.UNKNOWN,
    "inpi": LegalArea.UNKNOWN,
    "propriedade industrial": LegalArea.UNKNOWN,
    # Ambiental (no corpus → unknown)
    "licenciamento ambiental": LegalArea.UNKNOWN,
    "ambiental": LegalArea.UNKNOWN,
    # Eleitoral (no corpus → unknown)
    "eleitoral": LegalArea.UNKNOWN,
    "candidatura": LegalArea.UNKNOWN,
    # Internacional / migratório (no corpus → unknown)
    "naturalização": LegalArea.UNKNOWN,
    "naturalizacao": LegalArea.UNKNOWN,
    "extradição": LegalArea.UNKNOWN,
    "extradicao": LegalArea.UNKNOWN,
    # Marítimo (no corpus → unknown)
    "marítimo": LegalArea.UNKNOWN,
    "maritimo": LegalArea.UNKNOWN,
}


# Areas with an ingested corpus — statute/case-law retrieval is expected to find sources
# and the §14 gate may proceed to synthesis. Everything else (administrative, unknown)
# relies on retrieval coming back empty to trigger the safe refusal (§2.2).
IN_SCOPE_AREAS: frozenset[LegalArea] = frozenset(
    {
        LegalArea.CONSUMER,
        LegalArea.CIVIL,
        LegalArea.CRIMINAL,
        LegalArea.LABOR,
        LegalArea.TAX,
        LegalArea.CONSTITUTIONAL,
    }
)


def _score_area(question: str, keywords: dict[str, int]) -> int:
    return sum(weight for kw, weight in keywords.items() if kw in question)


def _out_of_scope_match(normalized: str) -> LegalArea | None:
    """Return the out-of-scope area when a corpus-less regime term is present.

    Terms proper to a regime without corpus prevail over incidental in-scope keywords
    (§2.2): on a tie/conflict we prefer refusal to leaking. ``administrative`` is reported
    as-is; every other corpus-less regime collapses to ``unknown``.
    """

    for term, area in _OUT_OF_SCOPE_TERMS.items():
        if term in normalized:
            return area
    return None


def classify_area(question: str) -> LegalArea:
    """Classify the legal area by weighted keyword evidence (§15.2).

    Out-of-scope regime terms (administrative, previdenciário, empresarial, etc.) take
    precedence over in-scope keyword evidence so incidental terms (e.g. "contrato" in a
    licitação question) cannot leak a corpus-less topic into an in-scope area (§2.2).
    """

    normalized = question.lower()
    out_of_scope = _out_of_scope_match(normalized)
    if out_of_scope is not None:
        return out_of_scope
    scored = {
        area: _score_area(normalized, kws) for area, kws in _AREA_KEYWORDS.items()
    }
    best_area = max(scored, key=lambda area: scored[area])
    if scored[best_area] == 0:
        return LegalArea.UNKNOWN
    return best_area


def is_in_scope(area: LegalArea) -> bool:
    """Whether the seed corpus is expected to cover this area (§15.2)."""

    return area in IN_SCOPE_AREAS


def run_classify_area(state: LegalResearchState) -> dict[str, Any]:
    """Graph node: set ``legal_area`` and an out-of-scope caveat when needed (§15.2)."""

    area = classify_area(state.question)
    update: dict[str, Any] = {"legal_area": area.value}
    if not is_in_scope(area):
        caveat = (
            "A base atual cobre Direito do Consumidor, Civil, Penal, Trabalhista, "
            "Tributário e Constitucional; "
            f"a pergunta parece ser de área '{area.value}', fora da cobertura."
        )
        update["caveats"] = [*state.caveats, caveat]
    return update
