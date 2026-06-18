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
from packages.ingestion.loaders.planalto_html import build_seed_markdown
from packages.ingestion.versioning import deduplicate_by_hash
from packages.legal_types.schemas import LegalChunk

# Repo-root-relative paths (this file lives at apps/worker/jobs/).
_REPO_ROOT = Path(__file__).resolve().parents[3]
SEED_PATH = _REPO_ROOT / "data" / "seed" / "cdc" / "cdc.md"
SOURCE_HTML_PATH = (
    _REPO_ROOT / "data" / "seed" / "cdc" / "_source" / "planalto_l8078compilado.html"
)
OUTPUT_PATH = _REPO_ROOT / "data" / "generated" / "cdc_chunks.jsonl"


def regenerate_seed_from_html(
    html_path: Path = SOURCE_HTML_PATH,
    seed_path: Path = SEED_PATH,
) -> bool:
    """Rebuild ``cdc.md`` from the vendored Planalto HTML if present.

    Deterministic regeneration: the markdown is a pure function of the HTML
    bytes, so re-running keeps the seed byte-identical (idempotency §40.4).
    Returns ``True`` if the seed was (re)generated, ``False`` otherwise.
    """

    if not html_path.is_file():
        return False
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text(build_seed_markdown(html_path), encoding="utf-8")
    return True


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
    html_path: Path | None = None,
) -> list[LegalChunk]:
    """Run the full ingestion and return the chunks written.

    If ``html_path`` is provided and exists, ``cdc.md`` is regenerated from it
    before chunking so the full Planalto-vendored CDC drives the output. The
    CLI ``main()`` handles HTML regeneration explicitly; callers (e.g. tests)
    pass ``html_path=None`` to skip it.
    """

    if html_path is not None:
        regenerate_seed_from_html(html_path, seed_path)
    chunks = build_chunks(seed_path, created_at=created_at)
    write_jsonl(chunks, output_path)
    return chunks


def main() -> int:
    # Fixed timestamp keeps the JSONL byte-stable across runs (idempotency proof).
    created_at = datetime(2026, 6, 16, tzinfo=UTC)
    regenerated = regenerate_seed_from_html()
    if regenerated:
        print(f"Regenerated {SEED_PATH} from {SOURCE_HTML_PATH}")
    chunks = run(created_at=created_at, html_path=None)
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
