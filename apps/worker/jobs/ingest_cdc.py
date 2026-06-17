"""CLI job: ingest the CDC seed into a structured JSONL of `LegalChunk`s.

``make ingest-cdc`` -> ``python -m apps.worker.jobs.ingest_cdc``.

Reads ``data/seed/cdc/cdc.md``, chunks it by article, deduplicates by
``content_hash`` (idempotent re-ingestion, §40.4) and writes one `LegalChunk`
per line to ``data/generated/cdc_chunks.jsonl``. The boundary with the indexer
is this JSONL — no embeddings or vector store here (§12.9).
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from packages.ingestion.chunker import chunk_document
from packages.ingestion.loaders.local_markdown import LocalMarkdownLoader
from packages.ingestion.versioning import deduplicate_by_hash
from packages.legal_types.schemas import LegalChunk

# Repo-root-relative paths (this file lives at apps/worker/jobs/).
_REPO_ROOT = Path(__file__).resolve().parents[3]
SEED_PATH = _REPO_ROOT / "data" / "seed" / "cdc" / "cdc.md"
OUTPUT_PATH = _REPO_ROOT / "data" / "generated" / "cdc_chunks.jsonl"


def build_chunks(
    seed_path: Path = SEED_PATH,
    *,
    created_at: datetime | None = None,
) -> list[LegalChunk]:
    """Load and chunk the CDC seed, deduplicated by content hash."""

    raw = LocalMarkdownLoader(seed_path).load()
    chunks = chunk_document(raw, created_at=created_at)
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
    """Run the full ingestion and return the chunks written."""

    chunks = build_chunks(seed_path, created_at=created_at)
    write_jsonl(chunks, output_path)
    return chunks


def main() -> int:
    # Fixed timestamp keeps the JSONL byte-stable across runs (idempotency proof).
    created_at = datetime(2026, 6, 16, tzinfo=UTC)
    chunks = run(created_at=created_at)
    articles = sorted(
        (c.article for c in chunks if c.article is not None),
        key=lambda a: int(a.rstrip("ºo°").split("-")[0]),
    )
    print(f"Ingested {len(chunks)} chunk(s) from {SEED_PATH}")
    print(f"Articles detected: {', '.join(articles)}")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
