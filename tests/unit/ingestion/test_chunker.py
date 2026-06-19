"""Structural chunking: article detection, metadata, stable ids, idempotency."""

from __future__ import annotations

from datetime import UTC, datetime

from packages.ingestion.chunker import chunk_document, iter_article_sections
from packages.ingestion.loaders.base import RawDocument
from packages.legal_types.enums import DocType, LegalArea, Source

_BODY = """Preâmbulo ignorado.

## Art. 6º

São direitos básicos do consumidor:

I - a proteção da vida;
II - a educação.

## Art. 12

O fabricante responde, independentemente de culpa.

§ 1º O produto é defeituoso quando não oferece a segurança esperada.

## Art. 14-A

Texto fictício de teste.
"""

_TS = datetime(2026, 6, 16, tzinfo=UTC)


def _raw(body: str = _BODY) -> RawDocument:
    return RawDocument(
        text=body,
        title="Código de Defesa do Consumidor",
        source=Source.PLANALTO,
        source_url="https://www.planalto.gov.br/ccivil_03/leis/l8078.htm",
        version="2026-06-16",
        norm_type="lei",
        norm_number="8078",
        norm_year="1990",
        short_name="cdc",
        legal_area=LegalArea.CONSUMER,
        jurisdiction="federal",
    )


def test_iter_sections_detects_articles() -> None:
    # The raw heading token carries the ordinal mark inside ``num`` ("6º"); the
    # ordinal sits before any letter suffix and is stripped downstream by
    # ``_match_article``/``_id_article``.
    nums = [n for n, _ in iter_article_sections(_BODY)]
    assert nums == ["6º", "12", "14-A"]


def test_chunk_metadata_and_ids() -> None:
    chunks = chunk_document(_raw(), created_at=_TS)
    by_id = {c.chunk_id: c for c in chunks}
    assert set(by_id) == {
        "cdc-8078-1990-art-6",
        "cdc-8078-1990-art-12",
        "cdc-8078-1990-art-14-a",
    }
    art6 = by_id["cdc-8078-1990-art-6"]
    assert art6.article == "6º"
    assert by_id["cdc-8078-1990-art-12"].article == "12"
    assert art6.doc_type is DocType.STATUTE
    assert art6.source is Source.PLANALTO
    assert art6.norm_number == "8078"
    assert art6.norm_year == "1990"
    assert art6.version == "2026-06-16"
    assert art6.legal_area is LegalArea.CONSUMER
    assert art6.content_hash.startswith("sha256:")
    assert art6.metadata["is_current"] is True


def test_internal_structure_preserved_in_text() -> None:
    chunks = chunk_document(_raw(), created_at=_TS)
    art12 = next(c for c in chunks if c.chunk_id == "cdc-8078-1990-art-12")
    assert "§ 1º" in art12.text
    art6 = next(c for c in chunks if c.chunk_id == "cdc-8078-1990-art-6")
    assert "I - a proteção da vida" in art6.text
    assert "II - a educação" in art6.text


def test_chunking_is_idempotent() -> None:
    a = chunk_document(_raw(), created_at=_TS)
    b = chunk_document(_raw(), created_at=_TS)
    assert [c.model_dump() for c in a] == [c.model_dump() for c in b]
    assert [c.content_hash for c in a] == [c.content_hash for c in b]


# Numbering that restarts across structural divisions (e.g. CF/88 body vs. ADCT)
# yields the same "Art. N" twice with different text — the chunk_id must not
# collide (it keys the vector-store point).
_RESTART_BODY = """## Art. 1º

Corpo permanente — primeiro artigo.

## Art. 2º

Corpo permanente — segundo artigo.

## Art. 1º

Disposições transitórias — primeiro artigo.
"""


def test_repeated_article_number_gets_stable_disambiguated_id() -> None:
    chunks = chunk_document(_raw(_RESTART_BODY), created_at=_TS)
    ids = [c.chunk_id for c in chunks]
    # No collision; first occurrence keeps the canonical id, the repeat is suffixed.
    assert len(ids) == len(set(ids))
    assert ids == [
        "cdc-8078-1990-art-1",
        "cdc-8078-1990-art-2",
        "cdc-8078-1990-art-1-occ-2",
    ]
    # Display article is unchanged for the disambiguated chunk.
    repeated = next(c for c in chunks if c.chunk_id.endswith("-occ-2"))
    assert repeated.article == "1º"
    assert "transitórias" in repeated.text


def test_disambiguation_is_idempotent() -> None:
    a = chunk_document(_raw(_RESTART_BODY), created_at=_TS)
    b = chunk_document(_raw(_RESTART_BODY), created_at=_TS)
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]


# High CC/CPC articles carry a thousands separator in the source heading
# ("## Art. 1.238"). The `article` field must be the dotless match token
# ("1238") so the ranking/filter path (which compares dotless) matches them,
# while the dotted citation surface survives in the rendered `text`.
_THOUSANDS_BODY = """## Art. 1.238

A propriedade adquire-se pela usucapião.

## Art. 1.240-A

Texto fictício de teste com sufixo.
"""


def test_thousands_article_is_dotless_match_token_with_dotted_heading() -> None:
    chunks = chunk_document(_raw(_THOUSANDS_BODY), created_at=_TS)
    by_id = {c.chunk_id: c for c in chunks}
    # Id and match token are dotless; suffix preserved.
    assert set(by_id) == {"cdc-8078-1990-art-1238", "cdc-8078-1990-art-1240-a"}
    art1238 = by_id["cdc-8078-1990-art-1238"]
    assert art1238.article == "1238"
    assert by_id["cdc-8078-1990-art-1240-a"].article == "1240-A"
    # The human-readable citation surface keeps the thousands dot in `text`.
    assert "## Art. 1.238" in art1238.text


def test_thousands_article_matches_ranker_citation_path() -> None:
    # Importing the consumer (packages.rag) to assert the contract end-to-end is
    # not editing it — the dotless `article` must win exact_citation_match for a
    # dotless query ("art 1238") and for the extractor on a dotted query too.
    from packages.rag.legal_ranker import exact_citation_match
    from packages.rag.query_analyzer import extract_article

    chunks = chunk_document(_raw(_THOUSANDS_BODY), created_at=_TS)
    payload = {"article": next(c.article for c in chunks if c.article == "1238")}

    assert extract_article("art 1238") == "1238"
    assert exact_citation_match(payload, extract_article("art 1238")) == 1.0
    assert exact_citation_match(payload, extract_article("art. 1.238")) == 1.0


def test_match_article_ordinal_before_letter_suffix() -> None:
    """Single-digit articles with a letter suffix render "1º-A", not "1-Aº"."""
    from packages.ingestion.chunker import _match_article

    assert _match_article("1-A") == "1º-A"
    assert _match_article("2-B") == "2º-B"
    # >= 10 carries no ordinal mark, with or without a suffix.
    assert _match_article("42-A") == "42-A"
    assert _match_article("10") == "10"
    # Plain single digit keeps the bare ordinal.
    assert _match_article("6") == "6º"
