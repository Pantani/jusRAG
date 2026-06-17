"""CLI job: ingest the STJ case-law seed into a JSONL of case_law `LegalChunk`s.

``python -m apps.worker.jobs.ingest_case_law``.

Reads ``data/seed/case_law/stj_consumer_seed.jsonl`` (public STJ súmulas, regra
§40), normalizes each into a `CaseLawDocument`, chunks its ementa into a single
`LegalChunk` with ``doc_type=case_law`` and the §9 case-law payload metadata, and
writes one chunk per line to ``data/generated/case_law_chunks.jsonl``. Output is
the SAME `LegalChunk` JSONL shape the indexer already consumes (§12.9); the
indexer filters jurisprudence via ``doc_type=case_law``. Idempotent by
``content_hash``. No embeddings / vector store here.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from packages.ingestion.chunker import chunk_case_law_documents
from packages.ingestion.loaders.stj import StjCaseLawLoader
from packages.ingestion.versioning import deduplicate_by_hash
from packages.legal_types.schemas import LegalChunk

# Repo-root-relative paths (this file lives at apps/worker/jobs/).
_REPO_ROOT = Path(__file__).resolve().parents[3]
SEED_PATH = _REPO_ROOT / "data" / "seed" / "case_law" / "stj_consumer_seed.jsonl"
OUTPUT_PATH = _REPO_ROOT / "data" / "generated" / "case_law_chunks.jsonl"


def build_chunks(
    seed_path: Path = SEED_PATH,
    *,
    created_at: datetime | None = None,
) -> list[LegalChunk]:
    """Load and chunk the STJ case-law seed, deduplicated by content hash."""

    docs = StjCaseLawLoader(seed_path).load()
    chunks = chunk_case_law_documents(docs, created_at=created_at)
    return list(deduplicate_by_hash(chunks))


def write_jsonl(chunks: list[LegalChunk], output_path: Path = OUTPUT_PATH) -> None:
    """Serialize chunks to JSONL (one `LegalChunk` per line, sorted by id)."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(chunks, key=lambda c: c.chunk_id)
    lines = [c.model_dump_json() for c in ordered]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    seed_path: Path = SEED_PATH,
    output_path: Path = OUTPUT_PATH,
    *,
    created_at: datetime | None = None,
) -> list[LegalChunk]:
    """Run the full case-law ingestion and return the chunks written."""

    chunks = build_chunks(seed_path, created_at=created_at)
    write_jsonl(chunks, output_path)
    return chunks


def main() -> int:
    # Fixed timestamp keeps the JSONL byte-stable across runs (idempotency proof).
    created_at = datetime(2026, 6, 16, tzinfo=UTC)
    chunks = run(created_at=created_at)
    courts = sorted({str(c.metadata.get("case_number", "")) for c in chunks})
    print(f"Ingested {len(chunks)} case_law chunk(s) from {SEED_PATH}")
    print(f"Entries detected: {', '.join(courts)}")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
