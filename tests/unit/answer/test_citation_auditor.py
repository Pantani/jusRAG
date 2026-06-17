"""Unit: CitationAuditor detects unsupported/hallucinated legal claims (§31, §21).

Covers the pure auditor (supported vs hallucinated article detection, coverage and
unsupported-rate arithmetic, ``passed`` flag) and the end-to-end enforcement: an
LLM fake forced to cite an article *outside* the recovered context proves the writer
rewrites the answer conservatively or refuses — never returns the hallucinated claim.
All offline, no network.
"""

from __future__ import annotations

import pytest

from packages.agents.citation_auditor import audit_answer
from packages.answer.answer_writer import AnswerWriter
from packages.answer.citation_auditor import (
    AuditChunk,
    LegalClaim,
    audit_claims,
)
from packages.answer.schemas import AnswerStatus
from packages.embeddings.fake_provider import FakeEmbeddingProvider
from packages.legal_types.schemas import LegalChunk
from packages.llm.base import DraftLegalBasis, LLMAnswerDraft, LLMMessage
from packages.rag.context_builder import BuiltContext
from packages.rag.retriever import LegalRetriever
from packages.rag.search_service import SearchService
from packages.storage.memory import InMemoryVectorStore

_ART12 = AuditChunk(
    chunk_id="cdc-8078-1990-art-12",
    text=(
        "## Art. 12\n\nO fabricante e o importador respondem, independentemente de culpa, "
        "pela reparação dos danos causados por defeitos do produto."
    ),
)


# --------------------------------------------------------------------------- pure auditor


def test_supported_claim_is_fully_covered() -> None:
    claim = LegalClaim(
        text="Segundo o art. 12, o fabricante responde pelos defeitos do produto.",
        cited_ids=("cdc-8078-1990-art-12",),
    )
    result = audit_claims("", [claim], [_ART12])

    assert result.unsupported_claims == []
    assert result.citation_coverage == pytest.approx(1.0)
    assert result.unsupported_legal_claim_rate == pytest.approx(0.0)
    assert result.passed is True


def test_hallucinated_article_is_detected() -> None:
    # Art. 99 was never recovered: the claim is unsupported even though its wording
    # overlaps the real product-defect chunk.
    hallucinated = LegalClaim(
        text="Conforme o art. 99, o fornecedor responde pelos defeitos do produto.",
    )
    result = audit_claims("", [hallucinated], [_ART12])

    assert hallucinated.text in result.unsupported_claims
    assert result.citation_coverage == pytest.approx(0.0)
    assert result.unsupported_legal_claim_rate == pytest.approx(1.0)
    assert result.passed is False


_SUMULA297 = AuditChunk(
    chunk_id="stj-sumula-297",
    text="Súmula 297: O Código de Defesa do Consumidor é aplicável às instituições financeiras.",
)


def test_supported_sumula_claim_is_covered() -> None:
    claim = LegalClaim(
        text="Conforme a Súmula 297 do STJ, o CDC é aplicável às instituições financeiras.",
        cited_ids=("stj-sumula-297",),
    )
    result = audit_claims("", [claim], [_SUMULA297])
    assert result.unsupported_claims == []
    assert result.passed is True


def test_hallucinated_sumula_is_detected() -> None:
    # Súmula 999 was never recovered: flagged even though wording overlaps the real one.
    hallucinated = LegalClaim(
        text="Conforme a Súmula 999 do STJ, o CDC é aplicável às instituições financeiras.",
    )
    result = audit_claims("", [hallucinated], [_SUMULA297])
    assert hallucinated.text in result.unsupported_claims
    assert result.passed is False


def test_metrics_are_fraction_of_claims() -> None:
    supported = LegalClaim(
        text="O art. 12 prevê que o fabricante responde pelos defeitos do produto.",
        cited_ids=("cdc-8078-1990-art-12",),
    )
    hallucinated = LegalClaim(
        text="O art. 99 garante indenização automática ao consumidor.",
    )
    result = audit_claims("", [supported, hallucinated], [_ART12])

    assert result.citation_coverage == pytest.approx(0.5)
    assert result.unsupported_legal_claim_rate == pytest.approx(0.5)
    assert result.unsupported_claims == [hallucinated.text]
    assert result.passed is False


def test_wrong_cited_chunk_cannot_be_rescued() -> None:
    # Claim cites art-18 but only art-12 is in context: the citation does not resolve.
    claim = LegalClaim(
        text="O art. 18 trata dos vícios de qualidade do produto.",
        cited_ids=("cdc-8078-1990-art-18",),
    )
    result = audit_claims("", [claim], [_ART12])

    assert result.passed is False
    assert claim.text in result.unsupported_claims


def test_no_legal_claim_is_vacuously_covered() -> None:
    result = audit_claims("Olá, como posso ajudar?", [], [_ART12])

    assert result.citation_coverage == pytest.approx(1.0)
    assert result.passed is True


# ------------------------------------------------------- end-to-end enforcement in writer


class _HallucinatingLLM:
    """LLM fake forced to assert an article that is NOT in the recovered context."""

    def generate_answer(
        self,
        messages: list[LLMMessage],
        context: BuiltContext,
    ) -> LLMAnswerDraft:
        # A genuinely grounded statement paraphrasing a recovered chunk (citing the
        # matching chunk id) plus a hallucinated one citing an absent article.
        grounded = next(
            c for c in context.chunks if c.citation.article == "12"
        )
        return LLMAnswerDraft(
            short_answer=(
                "Segundo o art. 12, o fabricante e o importador respondem pela "
                "reparação dos danos causados por defeitos do produto."
            ),
            legal_basis=[
                DraftLegalBasis(
                    text=(
                        "Segundo o art. 12, o fabricante e o importador respondem, "
                        "independentemente de culpa, pela reparação dos danos "
                        "causados por defeitos do produto."
                    ),
                    citations=[grounded.chunk_id],
                ),
                DraftLegalBasis(
                    text=(
                        "Conforme o art. 999 do CDC, o consumidor tem direito a "
                        "indenização automática e garantida em qualquer caso."
                    ),
                    citations=[grounded.chunk_id],
                ),
            ],
            caveats=[],
        )


@pytest.fixture
def writer_with_hallucinating_llm(cdc_chunks: list[LegalChunk]) -> AnswerWriter:
    embeddings = FakeEmbeddingProvider()
    store = InMemoryVectorStore()
    store.upsert_chunks(cdc_chunks, embeddings.embed_texts([c.text for c in cdc_chunks]))
    service = SearchService(LegalRetriever(embeddings, store))
    return AnswerWriter(service, _HallucinatingLLM())


def test_writer_drops_hallucinated_claim_and_attaches_audit(
    writer_with_hallucinating_llm: AnswerWriter,
) -> None:
    answer = writer_with_hallucinating_llm.write(
        "O fornecedor responde por defeito do produto?", top_k=3
    )

    # The hallucinated art. 999 claim must not survive into the final answer.
    texts = " ".join(b.text for b in answer.legal_basis)
    assert "999" not in texts
    assert answer.audit is not None
    # The final answer is internally consistent: its attached audit passes.
    assert answer.audit.passed is True
    # And it kept the genuinely supported art. 12 basis (or refused safely).
    if answer.status is AnswerStatus.ANSWERED:
        assert any("12" in b.text for b in answer.legal_basis)


class _SumulaHallucinatingLLM:
    """LLM fake that asserts a súmula NOT present in the recovered context (§2.1)."""

    def generate_answer(
        self,
        messages: list[LLMMessage],
        context: BuiltContext,
    ) -> LLMAnswerDraft:
        grounded = next(c for c in context.chunks if c.citation.article == "12")
        return LLMAnswerDraft(
            short_answer=(
                "Segundo o art. 12, o fabricante responde pelos defeitos do produto."
            ),
            legal_basis=[
                DraftLegalBasis(
                    text=(
                        "Segundo o art. 12, o fabricante e o importador respondem, "
                        "independentemente de culpa, pela reparação dos danos causados "
                        "por defeitos do produto."
                    ),
                    citations=[grounded.chunk_id],
                ),
                DraftLegalBasis(
                    text=(
                        "Conforme a Súmula 999 do STJ, o fornecedor responde "
                        "automaticamente por qualquer defeito do produto."
                    ),
                    citations=[grounded.chunk_id],
                ),
            ],
            caveats=[],
        )


def test_writer_removes_hallucinated_sumula(cdc_chunks: list[LegalChunk]) -> None:
    # (c) A súmula cited outside the recovered context is detected and removed.
    embeddings = FakeEmbeddingProvider()
    store = InMemoryVectorStore()
    store.upsert_chunks(cdc_chunks, embeddings.embed_texts([c.text for c in cdc_chunks]))
    service = SearchService(LegalRetriever(embeddings, store))
    writer = AnswerWriter(service, _SumulaHallucinatingLLM())

    answer = writer.write("O fornecedor responde por defeito do produto?", top_k=3)

    joined = " ".join(b.text for b in answer.legal_basis)
    assert "Súmula 999" not in joined and "999" not in joined
    assert answer.case_law == []  # no jurisprudence recovered -> no block invented
    assert answer.not_legal_advice is True
    assert answer.audit is not None and answer.audit.passed is True


def test_audit_answer_wrapper_matches_pure_auditor(
    writer_with_hallucinating_llm: AnswerWriter,
) -> None:
    answer = writer_with_hallucinating_llm.write(
        "O fornecedor responde por defeito do produto?", top_k=3
    )
    assert answer.audit is not None
    assert 0.0 <= answer.audit.citation_coverage <= 1.0
    assert answer.audit.unsupported_legal_claim_rate <= 0.05


def test_audit_answer_flags_hallucination_before_rewrite(
    cdc_chunks: list[LegalChunk],
) -> None:
    # Audit the *unfiltered* draft directly to prove detection happens pre-rewrite.
    from packages.answer.schemas import AnswerResponse, LegalBasisItem
    from packages.rag.context_builder import build_context
    from packages.rag.types import CitationRef, RetrievedChunk

    chunk = RetrievedChunk(
        chunk_id=_ART12.chunk_id,
        text=_ART12.text,
        score=0.9,
        semantic_score=0.9,
        citation=CitationRef(
            title="CDC",
            article="12",
            source_url=None,
            chunk_id=_ART12.chunk_id,
            doc_type="statute",
            source="planalto",
        ),
    )
    context = build_context([chunk])
    draft = AnswerResponse(
        status=AnswerStatus.ANSWERED,
        short_answer="ok",
        legal_basis=[
            LegalBasisItem(text="O art. 999 garante indenização.", citations=[_ART12.chunk_id]),
        ],
    )
    result = audit_answer(draft, context)
    assert result.passed is False
    assert any("999" in c for c in result.unsupported_claims)
