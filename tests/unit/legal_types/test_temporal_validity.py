"""Unit tests for temporal validity / versioning utilities."""

from datetime import UTC, date, datetime

from packages.legal_types.enums import DocType, Source
from packages.legal_types.schemas import LegalChunk
from packages.legal_types.temporal_validity import (
    current_chunks,
    is_current,
    latest_version,
    parse_version_date,
    select_version_at,
)

NOW = datetime(2026, 6, 16, tzinfo=UTC)


def _chunk(version: str, *, is_cur: bool | None = None) -> LegalChunk:
    metadata: dict[str, object] = {} if is_cur is None else {"is_current": is_cur}
    return LegalChunk(
        chunk_id=f"art-12@{version}",
        document_id="d",
        doc_type=DocType.STATUTE,
        source=Source.PLANALTO,
        title="t",
        article="12",
        text="...",
        version=version,
        content_hash="sha256:abc",
        created_at=NOW,
        metadata=metadata,
    )


def test_parse_version_date() -> None:
    assert parse_version_date("1990-09-11") == date(1990, 9, 11)


def test_is_current_default_true() -> None:
    assert is_current(_chunk("2026-06-16")) is True
    assert is_current(_chunk("1990-09-11", is_cur=False)) is False


def test_current_chunks_filters() -> None:
    chunks = [_chunk("1990-09-11", is_cur=False), _chunk("2026-06-16", is_cur=True)]
    result = current_chunks(chunks)
    assert len(result) == 1
    assert result[0].version == "2026-06-16"


def test_select_version_at() -> None:
    chunks = [_chunk("1990-09-11"), _chunk("2015-03-10"), _chunk("2026-06-16")]
    chosen = select_version_at(chunks, date(2020, 1, 1))
    assert chosen is not None
    assert chosen.version == "2015-03-10"


def test_select_version_before_existence() -> None:
    chunks = [_chunk("1990-09-11")]
    assert select_version_at(chunks, date(1980, 1, 1)) is None


def test_latest_version() -> None:
    chunks = [_chunk("1990-09-11"), _chunk("2026-06-16")]
    chosen = latest_version(chunks)
    assert chosen is not None
    assert chosen.version == "2026-06-16"
