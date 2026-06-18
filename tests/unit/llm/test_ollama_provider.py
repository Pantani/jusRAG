"""OllamaLLMProvider unit tests — fully offline via httpx.MockTransport (§8)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from packages.config.settings import Settings
from packages.llm.base import LLMMessage
from packages.llm.ollama_provider import OllamaLLMProvider
from packages.llm.selector import make_llm_provider
from packages.rag.context_builder import BuiltContext


def _empty_context() -> BuiltContext:
    return BuiltContext(text="", citations=[], chunks=[])


def _messages() -> list[LLMMessage]:
    return [LLMMessage(role="user", content="ping")]


def _make_provider(handler: Any) -> OllamaLLMProvider:
    transport = httpx.MockTransport(handler)
    return OllamaLLMProvider(
        base_url="http://ollama-test:11434",
        model="llama3.1:8b",
        transport=transport,
    )


def test_generate_answer_parses_structured_draft() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        content = json.dumps(
            {
                "short_answer": "resposta X",
                "legal_basis": [{"text": "fundamento", "citations": ["c1"]}],
                "caveats": ["ressalva"],
                "refused": False,
            }
        )
        return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})

    provider = _make_provider(handler)
    draft = provider.generate_answer(_messages(), _empty_context())

    assert draft.short_answer == "resposta X"
    assert draft.legal_basis[0].text == "fundamento"
    assert draft.legal_basis[0].citations == ["c1"]
    assert draft.caveats == ["ressalva"]
    assert draft.refused is False
    assert captured["url"] == "http://ollama-test:11434/api/chat"
    assert captured["body"]["model"] == "llama3.1:8b"
    assert captured["body"]["stream"] is False
    assert captured["body"]["format"] == "json"
    assert captured["body"]["options"]["temperature"] == 0
    assert captured["body"]["messages"] == [{"role": "user", "content": "ping"}]


def test_http_500_raises_runtime_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    provider = _make_provider(handler)
    with pytest.raises(RuntimeError, match="HTTP 500"):
        provider.generate_answer(_messages(), _empty_context())


def test_missing_message_content_raises_runtime_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    provider = _make_provider(handler)
    with pytest.raises(RuntimeError, match="message.content"):
        provider.generate_answer(_messages(), _empty_context())


def test_transport_error_raises_runtime_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    provider = _make_provider(handler)
    with pytest.raises(RuntimeError, match="failed"):
        provider.generate_answer(_messages(), _empty_context())


def test_timeout_env_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "60")
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    provider = OllamaLLMProvider(
        base_url="http://ollama-test:11434",
        model="llama3.1:8b",
        transport=transport,
    )
    assert provider.timeout == 60.0


def test_timeout_env_default_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_TIMEOUT_SECONDS", raising=False)
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    provider = OllamaLLMProvider(
        base_url="http://ollama-test:11434",
        model="llama3.1:8b",
        transport=transport,
    )
    assert provider.timeout == 300.0


def test_timeout_env_explicit_arg_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "60")
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    provider = OllamaLLMProvider(
        base_url="http://ollama-test:11434",
        model="llama3.1:8b",
        timeout=12.5,
        transport=transport,
    )
    assert provider.timeout == 12.5


def test_timeout_env_invalid_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "abc")
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    with pytest.raises(RuntimeError, match="OLLAMA_TIMEOUT_SECONDS"):
        OllamaLLMProvider(
            base_url="http://ollama-test:11434",
            model="llama3.1:8b",
            transport=transport,
        )


def test_timeout_env_non_positive_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "0")
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    with pytest.raises(RuntimeError, match="positive float"):
        OllamaLLMProvider(
            base_url="http://ollama-test:11434",
            model="llama3.1:8b",
            transport=transport,
        )


def test_selector_returns_ollama_provider_without_network() -> None:
    settings = Settings(
        llm_provider="ollama",
        ollama_base_url="http://ollama-test:11434",
        ollama_chat_model="llama3.1:8b",
    )
    provider = make_llm_provider(settings)
    assert isinstance(provider, OllamaLLMProvider)
