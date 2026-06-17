"""Front-matter parsing and offline loading of the markdown seed."""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.ingestion.loaders.local_markdown import (
    LocalMarkdownLoader,
    parse_front_matter,
)
from packages.legal_types.enums import LegalArea, Source

_DOC = """<!--
short_name: cdc
title: Código de Defesa do Consumidor
source: planalto
source_url: https://www.planalto.gov.br/ccivil_03/leis/l8078.htm
norm_type: lei
norm_number: 8078
norm_year: 1990
version: 2026-06-16
legal_area: consumer
jurisdiction: federal
-->

## Art. 6º

Direitos básicos.
"""


def test_parse_front_matter_splits_meta_and_body() -> None:
    meta, body = parse_front_matter(_DOC)
    assert meta["short_name"] == "cdc"
    assert meta["norm_number"] == "8078"
    assert "## Art. 6º" in body
    assert "short_name" not in body


def test_missing_block_raises() -> None:
    with pytest.raises(ValueError, match="missing provenance"):
        parse_front_matter("## Art. 6º\n\ntexto")


def test_missing_required_key_raises() -> None:
    with pytest.raises(ValueError, match="missing required provenance keys"):
        parse_front_matter("<!--\ntitle: X\n-->\nbody")


def test_loader_reads_seed(tmp_path: Path) -> None:
    seed = tmp_path / "cdc.md"
    seed.write_text(_DOC, encoding="utf-8")
    raw = LocalMarkdownLoader(seed).load()
    assert raw.source is Source.PLANALTO
    assert raw.legal_area is LegalArea.CONSUMER
    assert raw.short_name == "cdc"
    assert raw.norm_year == "1990"
    assert "## Art. 6º" in raw.text


def test_loader_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        LocalMarkdownLoader(tmp_path / "nope.md").load()
