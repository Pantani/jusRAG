"""IntakeAgent — legal triage node (§15.1).

Normalizes the question and extracts shallow ``facts``/``missing_facts`` without
touching the merits and without inventing anything (§15.1, §2.1). Deterministic and
offline: a real deployment swaps the heuristic for an LLM behind the same signature,
but the node contract — ``LegalResearchState`` in, partial update out — is stable.

Critical-fact detection drives the §14 ``needs_more_info`` route: when the question is
clearly in scope (a consumer matter) yet states no concrete fact to reason over, the
graph asks for more context instead of answering on air.
"""

from __future__ import annotations

import re
from typing import Any

from packages.agents.state import LegalResearchState

# Lightweight cues that a consumer question lacks the facts needed to be answered
# usefully. Kept conservative: we only ask for more info, never refuse on this alone.
_FACT_CUES = (
    "produto",
    "serviço",
    "servico",
    "compra",
    "contrato",
    "prazo",
    "data",
    "loja",
    "fornecedor",
    "defeito",
)

_QUESTION_MARKERS = ("?", "como", "qual", "quais", "posso", "tenho", "devo", "quando")


def normalize_question(question: str) -> str:
    """Collapse whitespace; preserve content (no merits inference)."""

    return re.sub(r"\s+", " ", question).strip()


def extract_facts(question: str) -> dict[str, Any]:
    """Extract shallow signals from the question (no fabrication, §2.1)."""

    normalized = question.lower()
    cues = sorted({cue for cue in _FACT_CUES if cue in normalized})
    is_question = any(marker in normalized for marker in _QUESTION_MARKERS)
    return {"fact_cues": cues, "is_question": is_question, "length": len(question)}


def detect_missing_facts(question: str, facts: dict[str, Any]) -> list[str]:
    """List missing facts that block a useful answer (drives §14 needs_more_info)."""

    cues = facts.get("fact_cues", [])
    if not cues and len(question.split()) < 4:
        return ["Detalhe a situação concreta: o que aconteceu, com qual produto/serviço."]
    return []


def run_intake(state: LegalResearchState) -> dict[str, Any]:
    """Graph node: triage the question into facts/missing_facts (§15.1)."""

    question = normalize_question(state.question)
    facts = extract_facts(question)
    missing = detect_missing_facts(question, facts)
    return {"question": question, "facts": facts, "missing_facts": missing}
