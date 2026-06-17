"""Local sentence-transformers embedding provider (implements EmbeddingProvider, §27).

Loads a HuggingFace ``sentence-transformers`` model in-process. The heavy
dependency is **lazy-imported** on first use: importing this module never
requires ``sentence-transformers`` to be installed, so unit tests stay offline
(system rules §6, §8) and the ``[local]`` extra remains optional.

The default model is the multilingual MPNet (``paraphrase-multilingual-mpnet-base-v2``),
chosen via ``settings.local_embedding_model`` for adequate Portuguese coverage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:  # pragma: no cover - typing only
    from sentence_transformers import SentenceTransformer


class LocalEmbeddingProvider:
    """sentence-transformers-backed provider with lazy model loading."""

    def __init__(self, model_name: str) -> None:
        if not model_name:
            raise ValueError("model_name must be a non-empty string")
        self._model_name = model_name
        self._loaded: SentenceTransformer | None = None

    def _model(self) -> SentenceTransformer:
        """Return the underlying model, loading it on first access."""

        if self._loaded is not None:
            return self._loaded
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers not installed; "
                "install with `pip install -e '.[local]'`"
            ) from exc
        self._loaded = SentenceTransformer(self._model_name)
        return self._loaded

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        encoded = cast(
            Any,
            self._model().encode(texts, normalize_embeddings=True),
        )
        return cast(list[list[float]], encoded.tolist())

    def embed_query(self, query: str) -> list[float]:
        encoded = cast(
            Any,
            self._model().encode([query], normalize_embeddings=True),
        )
        return cast(list[list[float]], encoded.tolist())[0]
