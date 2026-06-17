"""Formatter: build the structured AnswerResponse from an LLM draft + chunks (§30).

Guarantees the invariants the route relies on: ``sources`` is always present and
derived from the retrieved chunks' citations; the non-advice disclaimer (§41) is
always appended to ``caveats``; ``not_legal_advice`` is always true. It also drops
any draft legal-basis citation that does not point to a recovered chunk, so the
formatted answer can never reference a source outside the retrieved context (§2.1).
"""

from __future__ import annotations

from packages.answer.schemas import (
    AnswerResponse,
    AnswerStatus,
    CaseLawItem,
    LegalBasisItem,
    SourceItem,
)
from packages.legal_types.enums import DocType
from packages.llm.base import LLMAnswerDraft
from packages.rag.context_builder import BuiltContext
from packages.rag.types import RetrievedChunk

NON_ADVICE_DISCLAIMER = (
    "Esta resposta tem finalidade informativa e foi gerada com base nas fontes "
    "recuperadas pelo sistema. Ela não substitui a análise de um advogado ou "
    "profissional habilitado, especialmente porque a conclusão pode depender de "
    "fatos, documentos, datas e jurisprudência atualizada."
)

REFUSAL_SHORT_ANSWER = (
    "Não há base suficiente nas fontes recuperadas para responder a esta pergunta "
    "com segurança. Reformule a pergunta ou consulte um profissional habilitado."
)


def _sources_from_context(context: BuiltContext) -> list[SourceItem]:
    return [
        SourceItem(
            chunk_id=chunk.citation.chunk_id,
            title=chunk.citation.title,
            article=chunk.citation.article,
            source_url=chunk.citation.source_url,
            doc_type=chunk.citation.doc_type,
            source=chunk.citation.source,
        )
        for chunk in context.chunks
    ]


def _case_law_from_chunks(chunks: list[RetrievedChunk]) -> list[CaseLawItem]:
    """Build the jurisprudence block from *retrieved* case-law chunks only (§22, §32).

    Each item carries the citation already present in the indexed source (court,
    súmula/case number, ementa, source_url). Statute chunks are skipped, keeping
    legislation and jurisprudence visibly separated (§2.3). Never fabricated: an
    empty list means no jurisprudence was recovered and no block is shown.
    """

    items: list[CaseLawItem] = []
    for chunk in chunks:
        if chunk.citation.doc_type != DocType.CASE_LAW:
            continue
        meta = chunk.metadata
        items.append(
            CaseLawItem(
                chunk_id=chunk.chunk_id,
                court=_opt_str(meta.get("court")),
                case_number=_opt_str(meta.get("case_number")),
                title=chunk.citation.title,
                ementa=chunk.text,
                source_url=chunk.citation.source_url,
            )
        )
    return items


def _opt_str(value: object) -> str | None:
    return str(value) if value is not None else None


def build_refusal(context: BuiltContext) -> AnswerResponse:
    """A safe-refusal response: no fabricated legal basis, disclaimer attached."""

    return AnswerResponse(
        status=AnswerStatus.REFUSED,
        short_answer=REFUSAL_SHORT_ANSWER,
        legal_basis=[],
        case_law=[],
        caveats=[NON_ADVICE_DISCLAIMER],
        sources=_sources_from_context(context),
    )


def build_answer(
    draft: LLMAnswerDraft,
    context: BuiltContext,
    case_law_chunks: list[RetrievedChunk] | None = None,
) -> AnswerResponse:
    """Assemble the final structured answer, enforcing the §30/§41 invariants.

    ``case_law_chunks`` are the retrieved jurisprudence sources; the case_law block is
    populated strictly from them (§22). Defaults to none so callers without separated
    retrieval still get a legislation-only answer.
    """

    if draft.refused or not context.chunks:
        return build_refusal(context)

    # legal_basis carries legislation only; jurisprudence is rendered in case_law,
    # keeping the two sources visibly separated (§2.3). Citations to case-law chunks
    # are therefore dropped from legal_basis.
    statute_ids = {
        chunk.chunk_id
        for chunk in context.chunks
        if chunk.citation.doc_type != DocType.CASE_LAW
    }
    legal_basis = [
        LegalBasisItem(text=item.text, citations=in_context)
        for item in draft.legal_basis
        if (in_context := [c for c in item.citations if c in statute_ids])
    ]

    caveats = list(draft.caveats)
    caveats.append(NON_ADVICE_DISCLAIMER)

    return AnswerResponse(
        status=AnswerStatus.ANSWERED,
        short_answer=draft.short_answer,
        legal_basis=legal_basis,
        case_law=_case_law_from_chunks(case_law_chunks or []),
        caveats=caveats,
        sources=_sources_from_context(context),
    )
