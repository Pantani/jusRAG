"""Integration: article-range coverage per vendored federal code (Fase B P1).

A thousands-separator bug ("Art. 1.000" parsed as article "1") silently dropped
the entire CC Família/Sucessões range (arts. 1.000–2.046) and truncated the CPC.
The chunk *count* masked it (truncated articles became `-occ-K` duplicates of
art. 1). These tests read the real vendored HTML (offline, no network) and pin
landmark high-numbered articles so the hole cannot reopen unnoticed.

Lives under ``tests/integration`` (not ``tests/unit``): it loads the full
multi-MB vendored Planalto HTML of all 7 codes, too large for the "small,
reproducible seed" rule binding unit tests (§8). Still offline (vendored bytes,
no network) and collected by ``make test`` / CI because ``pyproject.toml`` sets
``testpaths = ["tests"]``.
"""

from __future__ import annotations

import re

import pytest

from packages.ingestion.chunker import chunk_document
from packages.ingestion.codes import CORE_CODES
from packages.ingestion.loaders.base import RawDocument
from packages.ingestion.loaders.planalto_html import html_to_markdown


def _articles_for(short_name: str) -> set[str]:
    entry = next(c for c in CORE_CODES if c.spec.short_name == short_name)
    body = html_to_markdown(entry.source_html.read_bytes())
    raw = RawDocument(
        source=entry.spec.source,
        title=entry.spec.title,
        short_name=entry.spec.short_name,
        legal_area=entry.spec.legal_area,
        jurisdiction=entry.spec.jurisdiction,
        norm_type=entry.spec.norm_type,
        norm_number=entry.spec.norm_number,
        norm_year=entry.spec.norm_year,
        text=body,
        source_url=entry.spec.source_url,
        version=entry.spec.version,
    )
    return {c.article for c in chunk_document(raw) if c.article}


# (short_name, landmark articles that MUST be present in the vendored source)
_LANDMARKS = [
    # The `article` field is the dotless match token (no thousands separator),
    # so the ranking/filter path matches high CC/CPC articles.
    ("cc", ["1000", "1511", "1711", "1784", "2046"]),  # Família + Sucessões
    ("cpc", ["1000", "1072"]),  # CPC tail
    ("cp", ["359", "361"]),
    ("cpp", ["800", "811"]),
    ("clt", ["900", "922"]),
    ("ctn", ["217", "218"]),
    ("cf88", ["249", "250"]),
]


@pytest.mark.parametrize(("short_name", "landmarks"), _LANDMARKS)
def test_high_numbered_articles_are_captured(
    short_name: str, landmarks: list[str]
) -> None:
    articles = _articles_for(short_name)
    missing = [a for a in landmarks if a not in articles]
    assert not missing, f"{short_name}: missing articles {missing}"


def test_cc_reaches_full_range() -> None:
    """CC must span up to art. 2.046, not stop at ~999 (the original bug)."""
    articles = _articles_for("cc")
    nums = {int(re.sub(r"\D", "", a.split("-")[0])) for a in articles}
    assert max(nums) == 2046
    assert len(nums) > 1900  # full code, not just the first book
