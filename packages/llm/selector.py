"""Config-driven selection of the LLM provider (§LLM_PROVIDER).

Mirrors ``packages/embeddings/selector.py`` for the answer layer so the API DI
(``apps/api/dependencies.py``) picks the provider from settings without coupling
the route to a concrete implementation.

- ``fake``   -> ``FakeLLMProvider`` (deterministic, no network, no key; offline /ask).
- ``openai`` -> ``OpenAILLMProvider`` (raises explicitly without a key; no silent
  fallback, per system rules §2/§6).
- ``ollama`` -> ``OllamaLLMProvider`` (local HTTP, Phase 12.3).
"""

from __future__ import annotations

from packages.config.settings import Settings, get_settings
from packages.llm.base import LLMProvider
from packages.llm.fake_provider import FakeLLMProvider
from packages.llm.ollama_provider import OllamaLLMProvider
from packages.llm.openai_provider import OpenAILLMProvider


def make_llm_provider(settings: Settings | None = None) -> LLMProvider:
    """Return the LLM provider selected by ``settings.llm_provider``."""

    settings = settings or get_settings()
    provider = settings.llm_provider
    if provider == "fake":
        return FakeLLMProvider()
    if provider == "openai":
        return OpenAILLMProvider(settings)
    if provider == "ollama":
        return OllamaLLMProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_chat_model,
        )
    raise RuntimeError(f"Unknown llm_provider: {provider!r}")


__all__ = ["make_llm_provider"]
