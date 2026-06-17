"""OpenAI-backed LLMProvider (§30, prompt §32). Never exercised in unit tests.

Reads ``OPENAI_API_KEY`` / ``OPENAI_CHAT_MODEL`` from settings. The ``openai``
client is imported lazily so importing this module never requires the dependency
or a key (system rules §6, §8). The model is constrained to return strict JSON
matching ``LLMAnswerDraft``; parsing failures surface explicitly (no silent
fallback). Grounding is enforced by the prompt and re-checked downstream by the
CitationAuditor (Phase 5).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from packages.config.settings import Settings, get_settings
from packages.llm.base import DraftLegalBasis, LLMAnswerDraft, LLMMessage
from packages.rag.context_builder import BuiltContext

if TYPE_CHECKING:  # pragma: no cover - typing only
    from openai import OpenAI


class OpenAILLMProvider:
    """Calls the OpenAI chat completions API for the answer writer."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set; cannot use OpenAILLMProvider. "
                "Configure it in .env or inject the FakeLLMProvider."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise RuntimeError("The 'openai' package is required for OpenAILLMProvider.") from exc
        self._client: OpenAI = OpenAI(api_key=self._settings.openai_api_key)
        self._model = self._settings.openai_chat_model

    def generate_answer(
        self,
        messages: list[LLMMessage],
        context: BuiltContext,  # noqa: ARG002 - real model uses prompt text
    ) -> LLMAnswerDraft:
        from openai.types.chat import ChatCompletionMessageParam

        payload = cast(
            "list[ChatCompletionMessageParam]",
            [{"role": m.role, "content": m.content} for m in messages],
        )
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=payload,
        )
        content = response.choices[0].message.content or ""
        return _parse_draft(content)


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
