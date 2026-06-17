"""OpenSearch BM25 store — prepared stub (optional, future phase).

BM25 lexical retrieval is an optional Phase-6 addition behind the same retrieval
contract. Intentionally not implemented: methods raise ``NotImplementedError``
rather than returning fake results, so no false signal leaks into ranking.
Enabled via ``Settings.enable_opensearch``.
"""

from __future__ import annotations

from typing import Any


class OpenSearchBM25Store:
    """Placeholder for a BM25 lexical store. Not implemented in Phase 3."""

    def search(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[Any]:
        raise NotImplementedError(
            "OpenSearch BM25 retrieval is not implemented yet (optional, Phase 6)."
        )
