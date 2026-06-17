"""Unit: formatter enforces sources, disclaimer, and context-bounded citations."""

from __future__ import annotations

from packages.answer.formatter import (
    NON_ADVICE_DISCLAIMER,
    build_answer,
    build_refusal,
)
from packages.answer.schemas import AnswerStatus
from packages.llm.base import DraftLegalBasis, LLMAnswerDraft
from packages.rag.context_builder import BuiltContext, build_context
from packages.rag.types import CitationRef, RetrievedChunk


def _chunk(article: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"cdc-8078-1990-art-{article}",
        text=f"## Art. {article}\n\ntexto",
        score=0.9,
        semantic_score=0.5,
        citation=CitationRef(
            title="CDC",
            article=article,
            source_url="https://example",
            chunk_id=f"cdc-8078-1990-art-{article}",
            doc_type="statute",
            source="planalto",
        ),
    )


def test_answer_always_has_sources_and_disclaimer() -> None:
    context = build_context([_chunk("12")])
    draft = LLMAnswerDraft(
        short_answer="resposta",
        legal_basis=[DraftLegalBasis("fundamento", ["cdc-8078-1990-art-12"])],
    )
    answer = build_answer(draft, context)

    assert answer.status is AnswerStatus.ANSWERED
    assert answer.not_legal_advice is True
    assert [s.chunk_id for s in answer.sources] == ["cdc-8078-1990-art-12"]
    assert NON_ADVICE_DISCLAIMER in answer.caveats


def test_drops_citations_outside_context() -> None:
    context = build_context([_chunk("12")])
    draft = LLMAnswerDraft(
        short_answer="resposta",
        legal_basis=[
            DraftLegalBasis("inventado", ["cdc-8078-1990-art-999"]),
            DraftLegalBasis("valido", ["cdc-8078-1990-art-12"]),
        ],
    )
    answer = build_answer(draft, context)

    # The fabricated-citation basis is dropped entirely; only the grounded one stays.
    assert len(answer.legal_basis) == 1
    assert answer.legal_basis[0].citations == ["cdc-8078-1990-art-12"]


def _case_law_chunk(number: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"stj-sumula-{number}",
        text="O CDC é aplicável às instituições financeiras.",
        score=0.8,
        semantic_score=0.6,
        citation=CitationRef(
            title=f"STJ Súmula {number}",
            article=None,
            source_url=f"https://stj/sumula-{number}.pdf",
            chunk_id=f"stj-sumula-{number}",
            doc_type="case_law",
            source="stj",
        ),
        metadata={"court": "STJ", "case_number": f"Súmula {number}"},
    )


def test_case_law_block_built_from_retrieved_jurisprudence() -> None:
    statute = _chunk("18")
    case_law = _case_law_chunk("297")
    context = build_context([statute, case_law])
    draft = LLMAnswerDraft(
        short_answer="resposta",
        legal_basis=[DraftLegalBasis("fundamento", ["cdc-8078-1990-art-18"])],
    )
    answer = build_answer(draft, context, [case_law])

    # Jurisprudence lands in case_law, separated from legal_basis (legislation only).
    assert [c.chunk_id for c in answer.case_law] == ["stj-sumula-297"]
    assert answer.case_law[0].court == "STJ"
    assert answer.case_law[0].case_number == "Súmula 297"
    assert answer.case_law[0].source_url == "https://stj/sumula-297.pdf"
    assert all("stj-sumula-297" not in b.citations for b in answer.legal_basis)


def test_no_case_law_chunks_means_no_block() -> None:
    context = build_context([_chunk("12")])
    draft = LLMAnswerDraft(
        short_answer="resposta",
        legal_basis=[DraftLegalBasis("fundamento", ["cdc-8078-1990-art-12"])],
    )
    answer = build_answer(draft, context)
    assert answer.case_law == []


def test_refused_draft_yields_refusal() -> None:
    context = build_context([_chunk("12")])
    answer = build_answer(LLMAnswerDraft(short_answer="x", refused=True), context)
    assert answer.status is AnswerStatus.REFUSED
    assert answer.legal_basis == []


def test_build_refusal_has_disclaimer_and_no_basis() -> None:
    answer = build_refusal(BuiltContext("", [], []))
    assert answer.status is AnswerStatus.REFUSED
    assert answer.legal_basis == []
    assert NON_ADVICE_DISCLAIMER in answer.caveats
    assert answer.not_legal_advice is True
