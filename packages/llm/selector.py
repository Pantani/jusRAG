"""Config-driven selection of the LLM provider (§LLM_PROVIDER).

Mirrors ``packages/embeddings/selector.py`` for the answer layer so the API DI
(``apps/api/dependencies.py``) picks the provider from settings without coupling
the route to a concrete implementation.

- ``fake``   -> ``FakeLLMProvider`` (deterministic, no network, no key; offline /ask).
- ``openai`` -> ``OpenAILLMProvider`` (raises explicitly without a key; no silent
  fallback, per system rules §2/§6).
"""

from __future__ import annotations

from packages.config.settings import Settings, get_settings
from packages.llm.base import LLMProvider
from packages.llm.fake_provider import FakeLLMProvider
from packages.llm.openai_provider import OpenAILLMProvider


def make_llm_provider(settings: Settings | None = None) -> LLMProvider:
    """Return the LLM provider selected by ``settings.llm_provider``."""

    settings = settings or get_settings()
    if settings.llm_provider == "fake":
        return FakeLLMProvider()
    return OpenAILLMProvider(settings)


__all__ = ["make_llm_provider"]
