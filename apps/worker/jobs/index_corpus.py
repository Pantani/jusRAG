"""CLI job: index the FULL statute corpus into Qdrant.

``make index-corpus`` -> ``python -m apps.worker.jobs.index_corpus``.

Thin alias over :mod:`apps.worker.jobs.index_cdc`: both indexers share the same
``load_indexable_chunks`` load set (CDC + the 7 federal codes from
``statutes_chunks.jsonl`` + available case law) into the single ``legal_chunks``
collection. The dedicated name makes the multi-area intent explicit at the
``make`` layer without forking the indexing logic (§5/§28).
"""

from __future__ import annotations

import sys

from apps.worker.jobs.index_cdc import main

if __name__ == "__main__":
    sys.exit(main())
