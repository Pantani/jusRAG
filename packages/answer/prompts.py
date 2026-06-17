"""Legal answer prompts (§32-§34, system rule §2).

Builds the system + user messages for the AnswerWriter. The system prompt encodes
the non-negotiable rules: answer only from the provided context, never invent a
source, keep legislation/jurisprudence/caveats separated, and refuse safely when
the context is insufficient. The user message carries the rendered context and the
question, and pins the strict JSON output shape consumed by the LLM providers.
"""

from __future__ import annotations

from packages.llm.base import LLMMessage
from packages.rag.context_builder import BuiltContext

ANSWER_SYSTEM_PROMPT = """\
Você é um redator jurídico assistivo para um sistema de pesquisa jurídica brasileira.

Responda em português brasileiro.
Use exclusivamente as fontes fornecidas no CONTEXTO.
Não invente artigos, leis, súmulas, decisões, teses ou números de processo.
Toda afirmação jurídica relevante deve estar apoiada em uma fonte do CONTEXTO, \
identificada pelo seu chunk_id.
Se o CONTEXTO não sustentar uma conclusão, diga que não há base suficiente e recuse.
Não forneça aconselhamento jurídico definitivo.
Separe claramente legislação (fundamento legal) de jurisprudência e de ressalvas.
Em "legal_basis", cite SOMENTE legislação (artigos de lei) presente no CONTEXTO.
Nunca afirme uma súmula, precedente ou tese de jurisprudência que não esteja \
explicitamente no CONTEXTO recuperado; se nenhuma jurisprudência foi recuperada, \
não mencione súmula nem precedente algum.
A jurisprudência relevante é montada automaticamente a partir das fontes recuperadas; \
não a invente no texto.
Use linguagem clara, técnica e conservadora; evite termos absolutos sem suporte na fonte.

Responda SOMENTE com um objeto JSON com o formato:
{
  "short_answer": "string",
  "legal_basis": [{"text": "string", "citations": ["chunk_id"]}],
  "caveats": ["string"],
  "refused": false
}
Se não houver base suficiente, retorne "refused": true e "legal_basis": [].
"""


def build_answer_messages(question: str, context: BuiltContext) -> list[LLMMessage]:
    """Assemble the system + user messages for a grounded legal answer."""

    context_text = context.text.strip() or "(nenhuma fonte recuperada)"
    user = (
        f"PERGUNTA:\n{question.strip()}\n\n"
        f"CONTEXTO (use apenas estas fontes; cada bloco indica seu chunk_id):\n"
        f"{_with_chunk_ids(context)}\n\n"
        f"{context_text}"
    )
    return [
        LLMMessage(role="system", content=ANSWER_SYSTEM_PROMPT),
        LLMMessage(role="user", content=user),
    ]


def _with_chunk_ids(context: BuiltContext) -> str:
    lines = [f"[{i}] chunk_id={chunk.chunk_id}" for i, chunk in enumerate(context.chunks, start=1)]
    return "\n".join(lines)
