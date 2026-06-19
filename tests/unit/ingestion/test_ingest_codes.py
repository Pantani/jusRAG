"""ingest_codes job: multi-area JSONL, decreto_lei, unique ids, idempotency.

Offline: tiny hand-crafted Planalto-style HTML fixtures (latin-1), no network.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from apps.worker.jobs.ingest_codes import iter_all_chunks, run
from packages.ingestion.codes import CORE_CODES, CodeEntry
from packages.ingestion.loaders.planalto_html import SeedSpec
from packages.legal_types.schemas import LegalChunk

_TS = datetime(2026, 6, 18, tzinfo=UTC)


def _html(*articles: str) -> bytes:
    paras = "\n".join(
        f'<p style="text-align: justify"><font>&nbsp;&nbsp;{a}</font></p>'
        for a in articles
    )
    return f"<html><body>{paras}</body></html>".encode("iso-8859-1")


def _make_entry(tmp_path: Path, short: str, norm_type: str, area: str, html: bytes) -> CodeEntry:
    src = tmp_path / area / "_source" / f"{short}.html"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(html)
    # Absolute path: ``CodeEntry.source_html`` does ``_REPO_ROOT / rel`` and
    # pathlib returns the absolute path unchanged, so the tmp fixture is found.
    rel = str(src)
    return CodeEntry(
        SeedSpec(
            short_name=short,
            title=f"Código {short.upper()}",
            source_url=f"https://www.planalto.gov.br/{short}.htm",
            norm_type=norm_type,
            norm_number="1234",
            norm_year="2000",
            legal_area=area,
            source_html_rel=rel,
        )
    )


@pytest.fixture
def entries(tmp_path: Path) -> tuple[CodeEntry, ...]:
    # tmp_path lives outside the repo; build rel paths anchored at repo root.
    # We instead override source_html via absolute by pointing rel at an abs path.
    cc = _make_entry(
        tmp_path, "cc", "lei", "civil",
        _html("Art. 1º Texto civil um.", "Art. 2º Texto civil dois."),
    )
    cp = _make_entry(
        tmp_path, "cp", "decreto_lei", "criminal",
        _html("Art. 1º Texto penal um.", "Art. 2º Texto penal dois."),
    )
    return cc, cp


def test_run_writes_multiarea_jsonl(tmp_path: Path, entries: tuple[CodeEntry, ...]) -> None:
    out = tmp_path / "statutes.jsonl"
    counts = run(out, entries=entries, created_at=_TS)
    assert counts == {"cc": 2, "cp": 2}
    lines = out.read_text(encoding="utf-8").splitlines()
    chunks = [LegalChunk.model_validate_json(line) for line in lines]
    assert len(chunks) == 4
    areas = {c.legal_area for c in chunks}
    assert areas == {"civil", "criminal"}


def test_decreto_lei_norm_type_preserved(tmp_path: Path, entries: tuple[CodeEntry, ...]) -> None:
    out = tmp_path / "statutes.jsonl"
    run(out, entries=entries, created_at=_TS)
    chunks = [
        LegalChunk.model_validate_json(line)
        for line in out.read_text(encoding="utf-8").splitlines()
    ]
    penal = [c for c in chunks if c.legal_area == "criminal"]
    assert penal and all(c.norm_type == "decreto_lei" for c in penal)
    civil = [c for c in chunks if c.legal_area == "civil"]
    assert civil and all(c.norm_type == "lei" for c in civil)


def test_chunk_ids_unique_and_provenance(tmp_path: Path, entries: tuple[CodeEntry, ...]) -> None:
    out = tmp_path / "statutes.jsonl"
    run(out, entries=entries, created_at=_TS)
    chunks = [
        LegalChunk.model_validate_json(line)
        for line in out.read_text(encoding="utf-8").splitlines()
    ]
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    for c in chunks:
        assert c.source == "planalto"
        assert c.source_url
        assert c.version
        assert c.content_hash.startswith("sha256:")


def test_idempotent_byte_stable(tmp_path: Path, entries: tuple[CodeEntry, ...]) -> None:
    out = tmp_path / "statutes.jsonl"
    run(out, entries=entries, created_at=_TS)
    first = out.read_bytes()
    run(out, entries=entries, created_at=_TS)
    assert out.read_bytes() == first


def test_global_hash_dedup_across_codes(tmp_path: Path) -> None:
    # Two codes sharing identical normalized article text -> deduped globally.
    same = _html("Art. 1º Texto idêntico compartilhado.")
    a = _make_entry(tmp_path, "aa", "lei", "civil", same)
    b = _make_entry(tmp_path, "bb", "lei", "tax", same)
    pairs = dict(iter_all_chunks((a, b), created_at=_TS))
    assert pairs["aa"] == [] or pairs["bb"] == []
    total = len(pairs["aa"]) + len(pairs["bb"])
    assert total == 1


def test_registry_covers_seven_core_codes() -> None:
    shorts = [e.spec.short_name for e in CORE_CODES]
    assert shorts == ["cf88", "cc", "cp", "clt", "ctn", "cpc", "cpp"]
    # decreto_lei is correctly assigned to CP/CPP/CLT (Phase A).
    dl = {e.spec.short_name for e in CORE_CODES if e.spec.norm_type == "decreto_lei"}
    assert dl == {"cp", "cpp", "clt"}
