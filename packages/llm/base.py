"""LLMProvider Protocol (§30, system rule §6, §10).

The answer writer depends only on this interface, never on a concrete client, so
the deterministic fake drives unit tests with no network. The provider receives a
fully-built prompt (system + context + question) and the structured retrieval
context, and returns a draft structured answer. Keeping the structured retrieval
context in the signature lets the fake ground its output strictly on the sources
(it never invents an article), while a real LLM uses the prompt text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from packages.rag.context_builder import BuiltContext


@dataclass(frozen=True)
class LLMMessage:
    """A single chat message (role + content)."""

    role: str
    content: str


@dataclass(frozen=True)
class DraftLegalBasis:
    """A grounded legal-basis statement and the chunk ids that support it."""

    text: str
    citations: list[str]


@dataclass(frozen=True)
class LLMAnswerDraft:
    """Structured draft produced by the LLM, before formatting/auditing.

    ``refused`` signals a safe refusal (insufficient grounding, §2.2/§40); when
    true the writer emits a refusal response and never fabricates legal basis.
    """

    short_answer: str
    legal_basis: list[DraftLegalBasis] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    refused: bool = False


@runtime_checkable
class LLMProvider(Protocol):
    """Generates a structured legal answer draft from a prompt + grounded context."""

    def generate_answer(
        self,
        messages: list[LLMMessage],
        context: BuiltContext,
    ) -> LLMAnswerDraft:
        """Produce a structured draft answer strictly grounded on ``context``."""
        ...
