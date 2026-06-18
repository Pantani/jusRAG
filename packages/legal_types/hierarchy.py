"""Normative authority hierarchy and weights (§39).

Drives the ``legal_authority`` term of the composite legal ranking score.
Weights are normalized to [0, 1]; higher means more authoritative/binding.
"""

from __future__ import annotations

from enum import StrEnum

from packages.legal_types.enums import DocType, PrecedentType
from packages.legal_types.schemas import CaseLawDocument, LegalChunk


class AuthorityTier(StrEnum):
    """Discrete normative authority tiers, ordered by weight (§39)."""

    CONSTITUTION = "constitution"
    FEDERAL_LAW = "federal_law"  # lei federal vigente / súmula vinculante / STF RG
    STJ_REPETITIVE = "stj_repetitive"
    STJ_SUMMARY = "stj_summary"
    STJ_CASE_LAW = "stj_case_law"
    TJ = "tj"
    DOCTRINE = "doctrine"
    BLOG = "blog"
    UNKNOWN = "unknown"


AUTHORITY_WEIGHTS: dict[AuthorityTier, float] = {
    AuthorityTier.CONSTITUTION: 1.00,
    AuthorityTier.FEDERAL_LAW: 0.95,
    AuthorityTier.STJ_REPETITIVE: 0.90,
    AuthorityTier.STJ_SUMMARY: 0.88,
    AuthorityTier.STJ_CASE_LAW: 0.75,
    AuthorityTier.TJ: 0.60,
    AuthorityTier.DOCTRINE: 0.40,
    AuthorityTier.BLOG: 0.20,
    AuthorityTier.UNKNOWN: 0.10,
}

# Authority order, most authoritative first.
AUTHORITY_ORDER: tuple[AuthorityTier, ...] = (
    AuthorityTier.CONSTITUTION,
    AuthorityTier.FEDERAL_LAW,
    AuthorityTier.STJ_REPETITIVE,
    AuthorityTier.STJ_SUMMARY,
    AuthorityTier.STJ_CASE_LAW,
    AuthorityTier.TJ,
    AuthorityTier.DOCTRINE,
    AuthorityTier.BLOG,
    AuthorityTier.UNKNOWN,
)


def weight_for(tier: AuthorityTier) -> float:
    """Return the authority weight for a tier."""

    return AUTHORITY_WEIGHTS[tier]


_STJ_PRECEDENT_TIERS: dict[PrecedentType, AuthorityTier] = {
    PrecedentType.REPETITIVE_APPEAL: AuthorityTier.STJ_REPETITIVE,
    PrecedentType.SUMMARY: AuthorityTier.STJ_SUMMARY,
    PrecedentType.BINDING_SUMMARY: AuthorityTier.FEDERAL_LAW,
    PrecedentType.BINDING_PRECEDENT: AuthorityTier.FEDERAL_LAW,
    PrecedentType.GENERAL_REPERCUSSION: AuthorityTier.FEDERAL_LAW,
}


# Norm types com força de lei federal vigente (§39). decreto_lei recepcionado
# (CP/CPP/CLT) pertence a este grupo, distinto de decreto regulamentar infralegal.
_FEDERAL_LAW_NORMS: frozenset[str] = frozenset(
    {"lei", "lei_complementar", "decreto_lei", "medida_provisoria"}
)


def tier_for_statute(chunk: LegalChunk) -> AuthorityTier:
    """Map a statute chunk to an authority tier (§39)."""

    norm = (chunk.norm_type or "").lower()
    if norm in {"constituicao", "constituição"}:
        return AuthorityTier.CONSTITUTION
    # decreto_lei recepcionado tem força de lei federal (CP/CPP/CLT), assim como
    # lei / lei_complementar / medida_provisoria. Explícito por robustez (§39).
    if norm in _FEDERAL_LAW_NORMS:
        return AuthorityTier.FEDERAL_LAW
    if norm:
        return AuthorityTier.FEDERAL_LAW
    return AuthorityTier.UNKNOWN


def tier_for_case_law(doc: CaseLawDocument) -> AuthorityTier:
    """Map a case-law document to an authority tier (§39)."""

    court = doc.court.upper()
    if doc.precedent_type in _STJ_PRECEDENT_TIERS:
        tier = _STJ_PRECEDENT_TIERS[doc.precedent_type]
        # STF general repercussion / binding instruments stay at federal-law tier.
        return tier
    if court == "STF":
        return AuthorityTier.FEDERAL_LAW
    if court == "STJ":
        return AuthorityTier.STJ_CASE_LAW
    if court.startswith("TJ"):
        return AuthorityTier.TJ
    return AuthorityTier.UNKNOWN


def authority_weight_for_chunk(chunk: LegalChunk) -> float:
    """Convenience: authority weight of a statute chunk."""

    return weight_for(tier_for_statute(chunk))


def authority_weight_for_doc_type(doc_type: DocType) -> float:
    """Coarse fallback when only ``doc_type`` is known."""

    fallback: dict[DocType, AuthorityTier] = {
        DocType.STATUTE: AuthorityTier.FEDERAL_LAW,
        DocType.CASE_LAW: AuthorityTier.STJ_CASE_LAW,
        DocType.PRECEDENT: AuthorityTier.STJ_REPETITIVE,
        DocType.DOCTRINE: AuthorityTier.DOCTRINE,
        DocType.UNKNOWN: AuthorityTier.UNKNOWN,
    }
    return weight_for(fallback[doc_type])
