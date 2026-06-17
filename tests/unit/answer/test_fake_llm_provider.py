"""Unit: FakeLLMProvider is deterministic, grounded, and refuses on empty context."""

from __future__ import annotations

from packages.llm.base import LLMMessage
from packages.llm.fake_provider import FakeLLMProvider
from packages.rag.context_builder import BuiltContext, build_context
from packages.rag.types import CitationRef, RetrievedChunk


def _chunk(article: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"cdc-8078-1990-art-{article}",
        text=text,
        score=0.9,
        semantic_score=0.5,
        citation=CitationRef(
            title="Código de Defesa do Consumidor",
            article=article,
            source_url="https://example/l8078",
            chunk_id=f"cdc-8078-1990-art-{article}",
            doc_type="statute",
            source="planalto",
        ),
    )


def test_refuses_on_empty_context() -> None:
    draft = FakeLLMProvider().generate_answer([], BuiltContext("", [], []))
    assert draft.refused is True
    assert draft.legal_basis == []


def test_grounds_each_basis_on_a_recovered_chunk() -> None:
    context = build_context([_chunk("12", "## Art. 12\n\nO fabricante responde por defeitos.")])
    draft = FakeLLMProvider().generate_answer([LLMMessage("system", "x")], context)

    assert draft.refused is False
    assert draft.legal_basis[0].citations == ["cdc-8078-1990-art-12"]
    # Never invents an article outside the context.
    for basis in draft.legal_basis:
        for cid in basis.citations:
            assert cid == "cdc-8078-1990-art-12"


def test_is_deterministic() -> None:
    context = build_context([_chunk("12", "## Art. 12\n\nO fabricante responde por defeitos.")])
    provider = FakeLLMProvider()
    a = provider.generate_answer([], context)
    b = provider.generate_answer([], context)
    assert a == b
