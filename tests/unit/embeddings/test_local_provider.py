"""LocalEmbeddingProvider: lazy load, explicit error, stubbed encode (§27).

All tests are offline: they never download a model, and case (b) runs even when
``sentence-transformers`` is not installed. Case (c) injects a fake
``sentence_transformers`` module into ``sys.modules`` so we exercise the
provider without the real dependency.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from packages.embeddings.base import EmbeddingProvider
from packages.embeddings.local_provider import LocalEmbeddingProvider
from packages.embeddings.selector import make_embedding_provider


class _StubSettings:
    """Minimal Settings stand-in for selector dispatch tests.

    Settings.embedding_provider is currently a Literal["openai", "fake"]; the
    selector reads it via ``str(...)`` so any object exposing the two attributes
    it needs is enough here.
    """

    def __init__(self, provider: str, model_name: str = "stub/model") -> None:
        self.embedding_provider = provider
        self.local_embedding_model = model_name


def test_selector_local_instantiates_without_loading_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Guard: make sentence_transformers unimportable. If the selector or the
    # constructor ever touched it eagerly, this would raise.
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    provider = make_embedding_provider(_StubSettings("local"))  # type: ignore[arg-type]
    assert isinstance(provider, LocalEmbeddingProvider)
    assert isinstance(provider, EmbeddingProvider)


def test_embed_raises_when_sentence_transformers_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Force the lazy import to fail with ImportError.
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    provider = LocalEmbeddingProvider(model_name="any/model")
    with pytest.raises(RuntimeError, match=r"sentence-transformers not installed"):
        provider.embed_texts(["hello"])


def test_embed_with_stubbed_sentence_transformers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _FakeArray:
        def __init__(self, data: list[list[float]]) -> None:
            self._data = data

        def tolist(self) -> list[list[float]]:
            return self._data

    class _FakeModel:
        def __init__(self, model_name: str) -> None:
            captured["model_name"] = model_name
            self.dim = 4

        def encode(
            self, texts: list[str], normalize_embeddings: bool = False
        ) -> _FakeArray:
            captured["normalize_embeddings"] = normalize_embeddings
            captured["last_texts"] = list(texts)
            # Deterministic, no network: each row is (i+1)/10 across `dim`.
            data = [[(i + 1) / 10.0] * self.dim for i in range(len(texts))]
            return _FakeArray(data)

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = _FakeModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    provider = LocalEmbeddingProvider(model_name="stub/model")
    vectors = provider.embed_texts(["a", "b"])
    assert vectors == [[0.1, 0.1, 0.1, 0.1], [0.2, 0.2, 0.2, 0.2]]
    assert captured["model_name"] == "stub/model"
    assert captured["normalize_embeddings"] is True

    query_vec = provider.embed_query("q")
    assert query_vec == [0.1, 0.1, 0.1, 0.1]
    assert captured["last_texts"] == ["q"]

    # Empty input short-circuits without calling encode again.
    captured["last_texts"] = ["sentinel"]
    assert provider.embed_texts([]) == []
    assert captured["last_texts"] == ["sentinel"]
