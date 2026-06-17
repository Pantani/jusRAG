"""Unit tests for the closed legal enums."""

from packages.legal_types.enums import (
    DocType,
    LegalArea,
    PrecedentType,
    SupportLevel,
)


def test_doc_type_covers_required_values() -> None:
    expected = {"statute", "case_law", "precedent", "doctrine", "unknown"}
    assert {d.value for d in DocType} == expected


def test_doc_type_is_str() -> None:
    assert DocType.STATUTE == "statute"
    assert isinstance(DocType.STATUTE, str)


def test_legal_area_covers_spec() -> None:
    expected = {
        "consumer",
        "civil",
        "labor",
        "constitutional",
        "tax",
        "criminal",
        "administrative",
        "unknown",
    }
    assert {a.value for a in LegalArea} == expected


def test_precedent_type_covers_spec() -> None:
    expected = {
        "binding_precedent",
        "repetitive_appeal",
        "general_repercussion",
        "binding_summary",
        "summary",
        "ordinary_case_law",
        "unknown",
    }
    assert {p.value for p in PrecedentType} == expected


def test_support_level_values() -> None:
    assert SupportLevel.DIRECT.value == "direct"
