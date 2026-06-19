"""Unit tests for the closed legal enums."""

from packages.legal_types.enums import (
    DocType,
    LegalArea,
    NormType,
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


def test_norm_type_covers_federal_codes() -> None:
    expected = {
        "constituicao",
        "lei",
        "lei_complementar",
        "decreto",
        "decreto_lei",
        "medida_provisoria",
        "unknown",
    }
    assert {n.value for n in NormType} == expected


def test_norm_type_decreto_lei_distinct_from_decreto() -> None:
    # CP (DL 2.848/1940), CPP (DL 3.689/1941), CLT (DL 5.452/1943).
    assert NormType.DECRETO_LEI.value == "decreto_lei"
    assert NormType.DECRETO_LEI is not NormType.DECRETO
