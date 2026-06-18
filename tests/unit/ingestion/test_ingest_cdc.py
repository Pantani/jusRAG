"""ingest_cdc job: JSONL output, idempotency, and the real CDC seed (offline)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import apps.worker.jobs.ingest_cdc as ingest_cdc
from apps.worker.jobs.ingest_cdc import SEED_PATH, build_chunks, main, run
from packages.legal_types.schemas import LegalChunk

_REQUIRED_ARTICLES = {"6º", "12", "14", "18", "26", "49"}
_TS = datetime(2026, 6, 16, tzinfo=UTC)

_SEED = """<!--
short_name: cdc
title: Código de Defesa do Consumidor
source: planalto
norm_type: lei
norm_number: 8078
norm_year: 1990
version: 2026-06-16
legal_area: consumer
jurisdiction: federal
-->

## Art. 12

Texto do art. 12.

## Art. 12

Texto do art. 12.

## Art. 49

Texto do art. 49.
"""


def _write_seed(tmp_path: Path) -> Path:
    seed = tmp_path / "cdc.md"
    seed.write_text(_SEED, encoding="utf-8")
    return seed


def test_run_writes_jsonl_one_chunk_per_line(tmp_path: Path) -> None:
    out = tmp_path / "out.jsonl"
    run(_write_seed(tmp_path), out, created_at=_TS)
    lines = out.read_text(encoding="utf-8").splitlines()
    # 3 article sections, but the duplicate art. 12 collapses by hash -> 2.
    assert len(lines) == 2
    for line in lines:
        LegalChunk.model_validate_json(line)


def test_dedup_by_hash(tmp_path: Path) -> None:
    chunks = build_chunks(_write_seed(tmp_path), created_at=_TS)
    ids = [c.chunk_id for c in chunks]
    assert ids.count("cdc-8078-1990-art-12") == 1


def test_reingestion_is_byte_stable(tmp_path: Path) -> None:
    out = tmp_path / "out.jsonl"
    seed = _write_seed(tmp_path)
    run(seed, out, created_at=_TS)
    first = out.read_bytes()
    run(seed, out, created_at=_TS)
    assert out.read_bytes() == first


def test_main_fails_fast_when_source_html_missing(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """`main()` returns 1 (no chunks published) if the Planalto HTML is absent."""

    monkeypatch.setattr(ingest_cdc, "SOURCE_HTML_PATH", tmp_path / "missing.html")
    monkeypatch.setattr(ingest_cdc, "SEED_PATH", tmp_path / "cdc.md")
    monkeypatch.setattr(ingest_cdc, "OUTPUT_PATH", tmp_path / "out.jsonl")
    rc = main()
    assert rc == 1
    err = capsys.readouterr().err
    assert "Missing source HTML" in err
    assert not (tmp_path / "out.jsonl").exists()


def test_real_seed_has_required_articles() -> None:
    # Offline: reads the committed seed file, no network.
    assert SEED_PATH.is_file(), f"missing seed at {SEED_PATH}"
    chunks = build_chunks(created_at=_TS)
    articles = {c.article for c in chunks}
    assert _REQUIRED_ARTICLES <= articles
    for c in chunks:
        assert c.content_hash.startswith("sha256:")
        assert c.norm_number == "8078"
        assert c.version
