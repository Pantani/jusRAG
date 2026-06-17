"""Closed legal vocabulary enums for the jus-rag-brasil domain.

All enums are string-valued so they serialize transparently into JSON payloads
(vector DB metadata, API responses) and compare cleanly against raw strings.
"""

from __future__ import annotations

from enum import StrEnum


class DocType(StrEnum):
    """Top-level document classification (§8/§9)."""

    STATUTE = "statute"
    CASE_LAW = "case_law"
    PRECEDENT = "precedent"
    DOCTRINE = "doctrine"
    UNKNOWN = "unknown"


class LegalArea(StrEnum):
    """Area of law. MVP focuses on ``consumer`` (CDC)."""

    CONSUMER = "consumer"
    CIVIL = "civil"
    LABOR = "labor"
    CONSTITUTIONAL = "constitutional"
    TAX = "tax"
    CRIMINAL = "criminal"
    ADMINISTRATIVE = "administrative"
    UNKNOWN = "unknown"


class Source(StrEnum):
    """Origin of the document. Open-ended in practice; these are the seeded ones."""

    PLANALTO = "planalto"
    STF = "stf"
    STJ = "stj"
    TJ = "tj"
    DOCTRINE = "doctrine"
    BLOG = "blog"
    UNKNOWN = "unknown"


class Jurisdiction(StrEnum):
    """Territorial/administrative scope of a norm."""

    FEDERAL = "federal"
    STATE = "state"
    MUNICIPAL = "municipal"
    UNKNOWN = "unknown"


class PrecedentType(StrEnum):
    """Binding/persuasive classification of case law (§15.5)."""

    BINDING_PRECEDENT = "binding_precedent"
    REPETITIVE_APPEAL = "repetitive_appeal"
    GENERAL_REPERCUSSION = "general_repercussion"
    BINDING_SUMMARY = "binding_summary"
    SUMMARY = "summary"
    ORDINARY_CASE_LAW = "ordinary_case_law"
    UNKNOWN = "unknown"


class SupportLevel(StrEnum):
    """How strongly a cited source backs a legal claim (used by the auditor)."""

    DIRECT = "direct"
    SUPPORTING = "supporting"
    RELATED = "related"
    UNSUPPORTED = "unsupported"


class NormType(StrEnum):
    """Type of legislative norm."""

    CONSTITUICAO = "constituicao"
    LEI = "lei"
    LEI_COMPLEMENTAR = "lei_complementar"
    DECRETO = "decreto"
    MEDIDA_PROVISORIA = "medida_provisoria"
    UNKNOWN = "unknown"
