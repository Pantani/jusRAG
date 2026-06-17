"""Unit tests for citation utilities."""

from datetime import UTC, date, datetime

from packages.legal_types.citations import (
    build_chunk_id,
    citation_from_case_law,
    citation_from_chunk,
    format_citation,
    slugify,
)
from packages.legal_types.enums import DocType, PrecedentType, Source, SupportLevel
from packages.legal_types.schemas import CaseLawDocument, LegalChunk

NOW = datetime(2026, 6, 16, tzinfo=UTC)


def test_build_chunk_id_article_only() -> None:
    cid = build_chunk_id(short_name="CDC", norm_number="8078", norm_year="1990", article="12")
    assert cid == "cdc-8078-1990-art-12"


def test_build_chunk_id_full_address() -> None:
    cid = build_chunk_id(
        short_name="cdc",
        norm_number="8078",
        norm_year="1990",
        article="6",
        paragraph="1",
        inciso="I",
    )
    assert cid == "cdc-8078-1990-art-6-par-1-inc-i"


def test_build_chunk_id_is_deterministic() -> None:
    kwargs = dict(short_name="cdc", norm_number="8078", norm_year="1990", article="49")
    assert build_chunk_id(**kwargs) == build_chunk_id(**kwargs)


def test_slugify() -> None:
    assert slugify("Art. 12 §1º") == "art-12-1"


def test_citation_from_chunk() -> None:
    chunk = LegalChunk(
        chunk_id="cdc-8078-1990-art-12",
        document_id="cdc-8078-1990",
        doc_type=DocType.STATUTE,
        source=Source.PLANALTO,
        title="CDC",
        article="12",
        text="...",
        version="2026-06-16",
        content_hash="sha256:abc",
        created_at=NOW,
        source_url="https://example/art12",
    )
    cit = citation_from_chunk(chunk)
    assert cit.citation_id == "cdc-8078-1990-art-12"
    assert cit.chunk_id == "cdc-8078-1990-art-12"
    assert cit.article == "12"
    assert cit.support_level is SupportLevel.DIRECT
    assert format_citation(cit) == "CDC, art. 12"


def test_citation_from_case_law() -> None:
    doc = CaseLawDocument(
        document_id="stj-resp-123",
        source=Source.STJ,
        court="STJ",
        case_number="REsp 123",
        precedent_type=PrecedentType.REPETITIVE_APPEAL,
        is_binding=True,
        judgment_date=date(2020, 1, 1),
        content_hash="sha256:def",
    )
    cit = citation_from_case_law(doc)
    assert cit.doc_type is DocType.CASE_LAW
    assert cit.case_number == "REsp 123"
    assert cit.support_level is SupportLevel.SUPPORTING
    assert format_citation(cit) == "STJ REsp 123"
