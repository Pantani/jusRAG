"""CLI job: bulk-index the legal corpus into OpenSearch for BM25 hybrid retrieval.

``python -m apps.worker.jobs.index_opensearch [--recreate]``

Reads ``data/generated/cdc_chunks.jsonl`` + optional ``case_law_chunks.jsonl``
(same source the Qdrant indexer consumes) and pushes them into the
``legal_chunks`` OpenSearch index. Idempotent at the ``chunk_id`` level (bulk
``index`` uses the chunk_id as ``_id``); ``--recreate`` drops the index first
when the mapping or analyzer changes.

Opt-in: only meaningful when ``enable_hybrid=true`` and OpenSearch is up
(``docker compose --profile hybrid up -d opensearch``).
"""

from __future__ import annotations

import argparse
import sys

from apps.worker.jobs.chunk_jsonl import load_indexable_chunks
from packages.config.settings import get_settings
from packages.storage.opensearch import OpenSearchBM25Store


def run(*, recreate: bool = False) -> int:
    settings = get_settings()
    store = OpenSearchBM25Store(url=settings.opensearch_url)
    if recreate:
        store.recreate_index()
    chunks = load_indexable_chunks()
    store.index_chunks(chunks)
    return len(chunks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="index_opensearch", description=__doc__)
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate the index before bulk indexing (mapping changes).",
    )
    args = parser.parse_args(argv)
    count = run(recreate=args.recreate)
    print(f"Indexed {count} chunk(s) into OpenSearch index 'legal_chunks'.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
