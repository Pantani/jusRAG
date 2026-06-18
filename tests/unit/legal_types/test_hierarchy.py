"""Unit tests for normative authority hierarchy and weights (§39)."""

from datetime import UTC, datetime

from packages.legal_types.enums import DocType, PrecedentType, Source
from packages.legal_types.hierarchy import (
    AUTHORITY_WEIGHTS,
    AuthorityTier,
    authority_weight_for_chunk,
    tier_for_case_law,
    tier_for_statute,
)
from packages.legal_types.schemas import CaseLawDocument, LegalChunk

NOW = datetime(2026, 6, 16, tzinfo=UTC)


def _chunk(norm_type: str | None) -> LegalChunk:
    return LegalChunk(
        chunk_id="x",
        document_id="d",
        doc_type=DocType.STATUTE,
        source=Source.PLANALTO,
        title="t",
        norm_type=norm_type,
        text="...",
        version="2026-06-16",
        content_hash="sha256:abc",
        created_at=NOW,
    )


def test_spec_weights() -> None:
    assert AUTHORITY_WEIGHTS[AuthorityTier.CONSTITUTION] == 1.00
    assert AUTHORITY_WEIGHTS[AuthorityTier.FEDERAL_LAW] == 0.95
    assert AUTHORITY_WEIGHTS[AuthorityTier.STJ_REPETITIVE] == 0.90
    assert AUTHORITY_WEIGHTS[AuthorityTier.STJ_SUMMARY] == 0.88
    assert AUTHORITY_WEIGHTS[AuthorityTier.STJ_CASE_LAW] == 0.75
    assert AUTHORITY_WEIGHTS[AuthorityTier.TJ] == 0.60
    assert AUTHORITY_WEIGHTS[AuthorityTier.DOCTRINE] == 0.40
    assert AUTHORITY_WEIGHTS[AuthorityTier.BLOG] == 0.20
    assert AUTHORITY_WEIGHTS[AuthorityTier.UNKNOWN] == 0.10


def test_statute_tiers() -> None:
    assert tier_for_statute(_chunk("constituicao")) is AuthorityTier.CONSTITUTION
    assert tier_for_statute(_chunk("lei")) is AuthorityTier.FEDERAL_LAW
    assert tier_for_statute(_chunk(None)) is AuthorityTier.UNKNOWN


def test_decreto_lei_maps_to_federal_law() -> None:
    # CP/CPP/CLT são decretos-lei recepcionados com força de lei federal (§39):
    # devem pesar 0.95, como lei federal vigente — não tier infralegal.
    assert tier_for_statute(_chunk("decreto_lei")) is AuthorityTier.FEDERAL_LAW
    assert authority_weight_for_chunk(_chunk("decreto_lei")) == 0.95
    assert tier_for_statute(_chunk("lei_complementar")) is AuthorityTier.FEDERAL_LAW
    assert tier_for_statute(_chunk("medida_provisoria")) is AuthorityTier.FEDERAL_LAW


def test_statute_weight_for_federal_law() -> None:
    assert authority_weight_for_chunk(_chunk("lei")) == 0.95


def _case(court: str, precedent: PrecedentType | None) -> CaseLawDocument:
    return CaseLawDocument(
        document_id="c",
        source=Source.STJ,
        court=court,
        precedent_type=precedent,
        content_hash="sha256:def",
    )


def test_case_law_tiers() -> None:
    assert tier_for_case_law(_case("STF", PrecedentType.GENERAL_REPERCUSSION)) is (
        AuthorityTier.FEDERAL_LAW
    )
    assert tier_for_case_law(_case("STJ", PrecedentType.REPETITIVE_APPEAL)) is (
        AuthorityTier.STJ_REPETITIVE
    )
    assert tier_for_case_law(_case("STJ", None)) is AuthorityTier.STJ_CASE_LAW
    assert tier_for_case_law(_case("TJSP", None)) is AuthorityTier.TJ
