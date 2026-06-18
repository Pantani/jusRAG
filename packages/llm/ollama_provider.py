"""Ollama-backed LLMProvider (§30, Phase 12.3). Local HTTP, no external network.

Talks to an Ollama server (``/api/chat``) configured via ``OLLAMA_BASE_URL`` /
``OLLAMA_CHAT_MODEL``. The model is constrained to return strict JSON matching
``LLMAnswerDraft`` (Ollama's ``format: "json"`` flag). Parsing or transport
failures surface explicitly — no silent fallback (system rules §2/§6).

Grounding is enforced by the prompt (built upstream by ``packages/answer``) and
re-checked downstream by the CitationAuditor (Phase 5). The ``BuiltContext`` is
accepted to match the ``LLMProvider`` Protocol but not consumed here — a real
model uses the prompt text.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from packages.llm.base import DraftLegalBasis, LLMAnswerDraft, LLMMessage
from packages.rag.context_builder import BuiltContext

DEFAULT_OLLAMA_TIMEOUT_SECONDS = 300.0
_TIMEOUT_ENV = "OLLAMA_TIMEOUT_SECONDS"


def _resolve_timeout(explicit: float | None) -> float:
    """Pick the HTTP timeout (seconds). Explicit arg > env > default.

    A malformed env value is a configuration error: surface it explicitly per
    system rules §2/§6 (no silent fallbacks).
    """

    if explicit is not None:
        return explicit
    raw = os.environ.get(_TIMEOUT_ENV)
    if raw is None or raw == "":
        return DEFAULT_OLLAMA_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid {_TIMEOUT_ENV}={raw!r}: must be a positive float (seconds)."
        ) from exc
    if value <= 0:
        raise RuntimeError(
            f"Invalid {_TIMEOUT_ENV}={raw!r}: must be a positive float (seconds)."
        )
    return value


class OllamaLLMProvider:
    """Calls a local Ollama server's chat endpoint for the answer writer."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = _resolve_timeout(timeout)
        self._client = httpx.Client(timeout=self._timeout, transport=transport)

    @property
    def timeout(self) -> float:
        return self._timeout

    def generate_answer(
        self,
        messages: list[LLMMessage],
        context: BuiltContext,  # noqa: ARG002 - real model uses prompt text
    ) -> LLMAnswerDraft:
        payload: dict[str, Any] = {
            "model": self._model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        content = self._post_chat(payload)
        return _parse_draft(content)

    def _post_chat(self, payload: dict[str, Any]) -> str:
        url = f"{self._base_url}/api/chat"
        try:
            response = self._client.post(url, json=payload)
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Ollama request to {url} failed: {exc}") from exc
        if response.status_code != 200:
            raise RuntimeError(
                f"Ollama returned HTTP {response.status_code} from {url}: "
                f"{response.text[:200]!r}"
            )
        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Ollama returned non-JSON body: {response.text[:200]!r}") from exc
        message = data.get("message")
        if not isinstance(message, dict) or "content" not in message:
            raise RuntimeError(f"Ollama response missing 'message.content': {data!r}")
        content = message["content"]
        if not isinstance(content, str):
            raise RuntimeError(f"Ollama 'message.content' is not a string: {content!r}")
        return content


def _parse_draft(content: str) -> LLMAnswerDraft:
    try:
        data: dict[str, Any] = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON content: {content!r}") from exc

    basis = [
        DraftLegalBasis(
            text=str(item.get("text", "")),
            citations=[str(c) for c in item.get("citations", [])],
        )
        for item in data.get("legal_basis", [])
    ]
    return LLMAnswerDraft(
        short_answer=str(data.get("short_answer", "")),
        legal_basis=basis,
        caveats=[str(c) for c in data.get("caveats", [])],
        refused=bool(data.get("refused", False)),
    )
