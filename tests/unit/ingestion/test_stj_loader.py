"""STJ case-law loader + ementa chunker: normalization, §9 metadata, idempotency.

Offline: the seed is a local JSONL of public STJ súmulas (regra §40) — no network,
no PII, no sealed-case numbers.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from pathlib import Path

from apps.worker.jobs.ingest_case_law import SEED_PATH, build_chunks, run
from packages.ingestion.chunker import chunk_case_law, chunk_case_law_documents
from packages.ingestion.loaders.stj import StjCaseLawLoader
from packages.legal_types.enums import DocType, PrecedentType, Source
from packages.legal_types.schemas import CaseLawDocument, LegalChunk

_TS = datetime(2026, 6, 16, tzinfo=UTC)

_SEED_LINE = (
    '{"summary_number": "297", "court": "STJ", "source": "stj", '
    '"precedent_type": "summary", "is_binding": false, "legal_area": "consumer", '
    '"judgment_date": "2004-05-12", "publication_date": "2004-09-09", '
    '"ementa": "O Código de Defesa do Consumidor é aplicável às '
    'instituições financeiras.", "source_url": "https://www.stj.jus.br/x.pdf"}\n'
)

# CPF / CNPJ / OAB-like markers that would signal PII or a sealed reference.
_PII_RE = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")


def _write_seed(tmp_path: Path) -> Path:
    seed = tmp_path / "stj_seed.jsonl"
    seed.write_text(_SEED_LINE, encoding="utf-8")
    return seed


def test_loader_normalizes_into_case_law_document(tmp_path: Path) -> None:
    docs = StjCaseLawLoader(_write_seed(tmp_path)).load()
    assert len(docs) == 1
    doc = docs[0]
    assert isinstance(doc, CaseLawDocument)
    assert doc.doc_type is DocType.CASE_LAW
    assert doc.source is Source.STJ
    assert doc.court == "STJ"
    assert doc.case_number == "Súmula 297"
    assert doc.document_id == "stj-sumula-297"
    assert doc.precedent_type is PrecedentType.SUMMARY
    assert doc.is_binding is False  # STJ ordinary súmula is not binding
    assert doc.judgment_date == date(2004, 5, 12)
    assert doc.content_hash.startswith("sha256:")
    assert "Código de Defesa do Consumidor" in (doc.ementa or "")


def test_ementa_chunk_carries_doc_type_and_section9_metadata(tmp_path: Path) -> None:
    doc = StjCaseLawLoader(_write_seed(tmp_path)).load()[0]
    chunk = chunk_case_law(doc, created_at=_TS)
    assert isinstance(chunk, LegalChunk)
    assert chunk.doc_type is DocType.CASE_LAW
    assert chunk.chunk_id == "stj-sumula-297"
    assert chunk.text  # ementa text present
    md = chunk.metadata
    assert md["court"] == "STJ"
    assert md["case_number"] == "Súmula 297"
    assert md["precedent_type"] == "summary"
    assert md["is_binding"] is False
    assert md["judgment_date"] == "2004-05-12"
    assert md["publication_date"] == "2004-09-09"
    assert chunk.source_url == "https://www.stj.jus.br/x.pdf"
    assert chunk.content_hash.startswith("sha256:")


def test_chunk_without_ementa_is_dropped() -> None:
    doc = CaseLawDocument(
        document_id="stj-sumula-000",
        source=Source.STJ,
        court="STJ",
        ementa=None,
        content_hash="sha256:deadbeef",
    )
    assert chunk_case_law(doc, created_at=_TS) is None
    assert chunk_case_law_documents([doc], created_at=_TS) == []


def test_reingestion_is_byte_stable(tmp_path: Path) -> None:
    out = tmp_path / "out.jsonl"
    seed = _write_seed(tmp_path)
    run(seed, out, created_at=_TS)
    first = out.read_bytes()
    run(seed, out, created_at=_TS)
    assert out.read_bytes() == first


def test_idempotent_by_hash(tmp_path: Path) -> None:
    # Duplicating the same súmula collapses to one chunk by content_hash.
    seed = tmp_path / "dup.jsonl"
    seed.write_text(_SEED_LINE + _SEED_LINE, encoding="utf-8")
    chunks = build_chunks(seed, created_at=_TS)
    assert len(chunks) == 1


def test_real_seed_is_case_law_and_pii_free() -> None:
    assert SEED_PATH.is_file(), f"missing seed at {SEED_PATH}"
    chunks = build_chunks(created_at=_TS)
    assert len(chunks) >= 30, f"expected >=30 seeded entries, got {len(chunks)}"
    summaries = [c for c in chunks if c.metadata.get("summary_number")]
    repetitives = [c for c in chunks if c.metadata.get("theme_number")]
    assert len(summaries) >= 15
    assert len(repetitives) >= 15
    for c in chunks:
        assert c.doc_type is DocType.CASE_LAW
        assert c.metadata["court"] == "STJ"
        assert c.source_url and c.source_url.startswith("https://")
        assert c.content_hash.startswith("sha256:")
        assert not _PII_RE.search(c.text), f"possible PII in chunk {c.chunk_id}"
        # Case number is either "Súmula N" or a paradigm REsp/Tema reference.
        case_number = c.metadata["case_number"]
        assert case_number.startswith("Súmula ") or "REsp" in case_number or case_number.startswith(
            "Tema "
        )


def test_repetitivo_entry_loads_with_theme_metadata(tmp_path: Path) -> None:
    line = (
        '{"theme_number": "938", "case_number": "REsp 1.578.553/SP", '
        '"court": "STJ", "source": "stj", "precedent_type": "repetitive_appeal", '
        '"is_binding": true, "legal_area": "consumer", '
        '"ementa": "Tese repetitiva exemplo.", '
        '"source_url": "https://www.stj.jus.br/repetitivos-temas/", '
        '"verification_status": "needs_review"}\n'
    )
    seed = tmp_path / "rep.jsonl"
    seed.write_text(line, encoding="utf-8")
    docs = StjCaseLawLoader(seed).load()
    assert len(docs) == 1
    doc = docs[0]
    assert doc.document_id == "stj-tema-938"
    assert doc.case_number == "REsp 1.578.553/SP"
    assert doc.precedent_type is PrecedentType.REPETITIVE_APPEAL
    assert doc.is_binding is True
    assert doc.metadata["theme_number"] == "938"
    assert doc.metadata["verification_status"] == "needs_review"
