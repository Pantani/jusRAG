"""Unit tests for legal-domain schemas — chunk/citation creation and minima."""

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from packages.legal_types import (
    CaseLawDocument,
    DocType,
    LegalArea,
    LegalChunk,
    LegalCitation,
    LegalDocument,
    PrecedentType,
    Source,
    SourceMetadata,
    SupportLevel,
)

NOW = datetime(2026, 6, 16, tzinfo=UTC)


def make_chunk(**overrides: object) -> LegalChunk:
    base: dict[str, object] = dict(
        chunk_id="cdc-8078-1990-art-12",
        document_id="cdc-8078-1990",
        doc_type=DocType.STATUTE,
        source=Source.PLANALTO,
        title="Código de Defesa do Consumidor",
        legal_area=LegalArea.CONSUMER,
        jurisdiction="federal",
        norm_type="lei",
        norm_number="8078",
        norm_year="1990",
        article="12",
        text="O fabricante responde pelo defeito do produto...",
        version="2026-06-16",
        content_hash="sha256:abc",
        created_at=NOW,
    )
    base.update(overrides)
    return LegalChunk(**base)  # type: ignore[arg-type]


def test_legal_chunk_minimal_fields() -> None:
    chunk = make_chunk()
    assert chunk.chunk_id == "cdc-8078-1990-art-12"
    assert chunk.doc_type is DocType.STATUTE
    assert chunk.country == "BR"
    assert chunk.paragraph is None
    assert chunk.metadata == {}


def test_legal_chunk_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        make_chunk(text="")


def test_legal_chunk_requires_content_hash() -> None:
    with pytest.raises(ValidationError):
        LegalChunk(  # type: ignore[call-arg]
            chunk_id="x",
            document_id="d",
            doc_type=DocType.STATUTE,
            source=Source.PLANALTO,
            title="t",
            version="2026-06-16",
            text="body",
            created_at=NOW,
        )


def test_legal_document_defaults() -> None:
    doc = LegalDocument(
        document_id="cdc-8078-1990",
        doc_type=DocType.STATUTE,
        source=Source.PLANALTO,
        title="CDC",
        version="2026-06-16",
        content_hash="sha256:abc",
        created_at=NOW,
    )
    assert doc.country == "BR"
    assert doc.legal_area is None


def test_case_law_doc_type_is_fixed() -> None:
    doc = CaseLawDocument(
        document_id="stj-resp-123",
        source=Source.STJ,
        court="STJ",
        case_number="REsp 123",
        precedent_type=PrecedentType.REPETITIVE_APPEAL,
        is_binding=True,
        content_hash="sha256:def",
    )
    assert doc.doc_type is DocType.CASE_LAW
    assert doc.is_binding is True


def test_legal_citation_minimal() -> None:
    cit = LegalCitation(
        citation_id="cdc-8078-1990-art-12",
        source=Source.PLANALTO,
        doc_type=DocType.STATUTE,
        title="CDC",
        article="12",
        support_level=SupportLevel.DIRECT,
        chunk_id="cdc-8078-1990-art-12",
    )
    assert cit.support_level is SupportLevel.DIRECT
    assert cit.judgment_date is None


def test_legal_citation_accepts_dates() -> None:
    cit = LegalCitation(
        citation_id="stj-123",
        source=Source.STJ,
        doc_type=DocType.CASE_LAW,
        title="REsp 123",
        court="STJ",
        case_number="REsp 123",
        judgment_date=date(2020, 1, 1),
        publication_date=date(2020, 2, 1),
        support_level=SupportLevel.SUPPORTING,
    )
    assert cit.judgment_date == date(2020, 1, 1)


def test_source_metadata() -> None:
    meta = SourceMetadata(
        source=Source.PLANALTO,
        version="2026-06-16",
        content_hash="sha256:abc",
        ingested_at=NOW,
    )
    assert meta.is_current is True
