"""CLI job: ingest the core federal codes into one multi-area JSONL (§12.3, §40.4).

``make ingest-codes`` -> ``python -m apps.worker.jobs.ingest_codes``.

For each code in :data:`packages.ingestion.codes.CORE_CODES` this:
1. regenerates the seed markdown (``data/seed/<dir>/<short_name>.md``) from the
   vendored Planalto HTML deterministically (idempotent, §40.4);
2. chunks it article-by-article into ``LegalChunk``s carrying the code's
   ``legal_area``/``norm_type`` (incl. ``decreto_lei`` for CP/CPP/CLT),
   ``norm_number``/``norm_year``, ``source=planalto``, ``source_url``,
   ``version``, ``content_hash`` and ``ingested_at``;
3. appends them to a single ``data/generated/statutes_chunks.jsonl``.

**One JSONL, multi-area.** The indexer (`chunk_jsonl.load_indexable_chunks`)
concatenates statute + case-law JSONLs into the one ``legal_chunks`` collection,
so a single statutes file matches the consumer cleanly and keeps `legal_area` as
a payload filter (FILTERABLE_KEYS). The boundary with the indexer is this JSONL —
no embeddings or vector store here (§12.9).

Idempotency: ``content_hash`` dedup is global across codes; a fixed
``ingested_at`` keeps the file byte-stable across runs. If a vendored HTML is
missing the job fails fast (no stale/invented chunks, §2/§40.4).
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from packages.ingestion.chunker import chunk_document
from packages.ingestion.codes import CORE_CODES, CodeEntry
from packages.ingestion.loaders.local_markdown import LocalMarkdownLoader
from packages.ingestion.loaders.planalto_html import build_seed_markdown
from packages.legal_types.schemas import LegalChunk

_REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_PATH = _REPO_ROOT / "data" / "generated" / "statutes_chunks.jsonl"

# Fixed timestamp -> byte-stable JSONL across runs (idempotency proof, §40.4).
_FIXED_TS = datetime(2026, 6, 18, tzinfo=UTC)


def regenerate_seed(entry: CodeEntry) -> None:
    """Rebuild the code's seed markdown from its vendored HTML (deterministic)."""

    entry.seed_markdown.parent.mkdir(parents=True, exist_ok=True)
    md = build_seed_markdown(entry.source_html, entry.spec)
    entry.seed_markdown.write_text(md, encoding="utf-8")


def chunk_code(entry: CodeEntry, *, created_at: datetime) -> list[LegalChunk]:
    """Regenerate the seed from HTML and chunk it article-by-article."""

    regenerate_seed(entry)
    raw = LocalMarkdownLoader(entry.seed_markdown).load()
    return chunk_document(raw, created_at=created_at)


def iter_all_chunks(
    entries: tuple[CodeEntry, ...] = CORE_CODES,
    *,
    created_at: datetime = _FIXED_TS,
) -> Iterator[tuple[str, list[LegalChunk]]]:
    """Yield ``(short_name, chunks)`` per code, hash-deduplicated globally.

    Dedup is global (shared ``seen`` set) so identical normalized text never
    duplicates across codes; chunk_ids stay code-namespaced so distinct articles
    never collide. Streaming keeps peak memory to one code at a time.
    """

    seen: set[str] = set()
    for entry in entries:
        kept: list[LegalChunk] = []
        for chunk in chunk_code(entry, created_at=created_at):
            if chunk.content_hash in seen:
                continue
            seen.add(chunk.content_hash)
            kept.append(chunk)
        yield entry.spec.short_name, kept


def run(
    output_path: Path = OUTPUT_PATH,
    *,
    entries: tuple[CodeEntry, ...] = CORE_CODES,
    created_at: datetime = _FIXED_TS,
) -> dict[str, int]:
    """Ingest all codes into one JSONL. Returns per-code chunk counts."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    all_chunks: list[LegalChunk] = []
    for short_name, chunks in iter_all_chunks(entries, created_at=created_at):
        counts[short_name] = len(chunks)
        all_chunks.extend(chunks)
    ordered = sorted(all_chunks, key=lambda c: c.chunk_id)
    lines = [c.model_dump_json() for c in ordered]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return counts


def _missing_sources(entries: tuple[CodeEntry, ...]) -> list[str]:
    return [e.spec.short_name for e in entries if not e.source_html.is_file()]


def main() -> int:
    missing = _missing_sources(CORE_CODES)
    if missing:
        print(
            f"Missing vendored Planalto HTML for: {', '.join(missing)}. "
            "Vendore o HTML oficial antes de rodar `make ingest-codes` — publicar "
            "chunks a partir de fonte ausente viola §2/§40.4.",
            file=sys.stderr,
        )
        return 1
    counts = run()
    total = sum(counts.values())
    print(f"Ingested {total} chunk(s) across {len(counts)} codes -> {OUTPUT_PATH}")
    for short_name, n in counts.items():
        print(f"  {short_name}: {n} chunks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
