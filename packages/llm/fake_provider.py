"""FakeLLMProvider — deterministic, network-free LLM stand-in (§20, system rule §8).

It never calls a model and never invents an article: the draft is synthesized
*only* from the retrieved ``BuiltContext``. Each retrieved chunk becomes a grounded
``legal_basis`` entry citing its own ``chunk_id``. When the context is empty (no
source recovered) it returns ``refused=True`` so the writer can prove safe refusal
(§2.2, §2.3, §40). This lets tests assert both the structured shape and refusal
without a real LLM.
"""

from __future__ import annotations

import re

from packages.llm.base import (
    DraftLegalBasis,
    LLMAnswerDraft,
    LLMMessage,
    LLMProvider,
)
from packages.rag.context_builder import BuiltContext
from packages.rag.types import RetrievedChunk

_SENTENCE_SPLIT = re.compile(r"(?<=[.;])\s+")
_HEADING = re.compile(r"^##\s*Art\.?\s*\S+\s*", re.IGNORECASE)


def _first_sentence(text: str) -> str:
    """First meaningful sentence of a chunk, stripping the ``## Art. N`` heading."""

    body = _HEADING.sub("", text.strip()).strip()
    body = body.replace("\n", " ").strip()
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(body) if p.strip()]
    return parts[0] if parts else body


class FakeLLMProvider(LLMProvider):
    """Deterministic provider: paraphrases only what the context contains."""

    def generate_answer(
        self,
        messages: list[LLMMessage],
        context: BuiltContext,
    ) -> LLMAnswerDraft:
        if not context.chunks:
            return LLMAnswerDraft(
                short_answer=(
                    "Não há base suficiente nas fontes recuperadas para responder a "
                    "esta pergunta com segurança."
                ),
                legal_basis=[],
                caveats=[],
                refused=True,
            )

        basis: list[DraftLegalBasis] = []
        for chunk in context.chunks:
            label = _source_label(chunk)
            sentence = _first_sentence(chunk.text)
            basis.append(
                DraftLegalBasis(
                    text=f"Segundo {label}: {sentence}",
                    citations=[chunk.chunk_id],
                )
            )

        top = context.chunks[0]
        short = f"Com base em {_source_label(top)}, {_first_sentence(top.text)}"
        caveats = [
            "A conclusão pode depender de fatos, documentos e datas do caso concreto.",
        ]
        return LLMAnswerDraft(short_answer=short, legal_basis=basis, caveats=caveats)


def _source_label(chunk: RetrievedChunk) -> str:
    citation = chunk.citation
    if citation.article:
        return f"{citation.title}, art. {citation.article}"
    return citation.title
