"""Integration: POST /ask via TestClient, offline (fake embedding/store/LLM).

Overrides the real OpenAI/Qdrant/LLM dependencies with deterministic fakes, so no
network or running infra is needed (system rule §8). Proves the §20 acceptance:
(a) full structured shape with sources + not_legal_advice=true, (b) in-scope
question cites art. 12, (c) out-of-scope question -> safe refusal, (d) no citation
outside the recovered context.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import (
    get_embedding_provider,
    get_llm_provider,
    get_vector_store,
)
from apps.api.main import create_app
from packages.embeddings.fake_provider import FakeEmbeddingProvider
from packages.legal_types.enums import DocType, LegalArea, Source
from packages.legal_types.schemas import LegalChunk
from packages.llm.fake_provider import FakeLLMProvider
from packages.storage.memory import InMemoryVectorStore

_SEED = {
    "12": "## Art. 12\n\nO fabricante e o importador respondem, independentemente de culpa, "
    "por defeitos do produto.",
    "18": "## Art. 18\n\nOs fornecedores respondem pelos vícios de qualidade dos produtos.",
    "49": "## Art. 49\n\nO consumidor pode desistir do contrato, exercendo o direito de "
    "arrependimento, no prazo de sete dias.",
}


def _chunk(article: str, text: str) -> LegalChunk:
    return LegalChunk(
        chunk_id=f"cdc-8078-1990-art-{article}",
        document_id="cdc-8078-1990",
        doc_type=DocType.STATUTE,
        source=Source.PLANALTO,
        title="Código de Defesa do Consumidor (Lei nº 8.078/1990)",
        legal_area=LegalArea.CONSUMER,
        norm_type="lei",
        norm_number="8078",
        norm_year="1990",
        article=article,
        text=text,
        source_url="https://www.planalto.gov.br/ccivil_03/leis/l8078.htm",
        version="2026-06-16",
        content_hash=f"sha256:fixture-{article}",
        created_at=datetime(2026, 6, 16, tzinfo=UTC),
        metadata={"is_current": True},
    )


def _case_law_chunk(number: str, ementa: str) -> LegalChunk:
    return LegalChunk(
        chunk_id=f"stj-sumula-{number}",
        document_id=f"stj-sumula-{number}",
        doc_type=DocType.CASE_LAW,
        source=Source.STJ,
        title=f"STJ Súmula {number}",
        legal_area=LegalArea.CONSUMER,
        text=ementa,
        source_url=f"https://www.stj.jus.br/sumula-{number}.pdf",
        version="1995-03-29",
        content_hash=f"sha256:fixture-sumula-{number}",
        created_at=datetime(2026, 6, 16, tzinfo=UTC),
        metadata={
            "is_current": True,
            "court": "STJ",
            "case_number": f"Súmula {number}",
            "precedent_type": "summary",
            "is_binding": False,
        },
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    provider = FakeEmbeddingProvider()
    store = InMemoryVectorStore()
    chunks: list[LegalChunk] = [_chunk(a, t) for a, t in _SEED.items()]
    chunks.append(
        _case_law_chunk(
            "297",
            "O Código de Defesa do Consumidor é aplicável às instituições financeiras.",
        )
    )
    store.upsert_chunks(chunks, provider.embed_texts([c.text for c in chunks]))

    app = create_app()
    app.dependency_overrides[get_embedding_provider] = lambda: provider
    app.dependency_overrides[get_vector_store] = lambda: store
    llm = FakeLLMProvider()
    app.dependency_overrides[get_llm_provider] = lambda: llm
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_ask_structured_shape(client: TestClient) -> None:
    resp = client.post("/ask", json={"question": "defeito do produto", "top_k": 3})
    assert resp.status_code == 200
    body = resp.json()
    for key in ("status", "short_answer", "legal_basis", "case_law", "caveats", "sources"):
        assert key in body
    assert body["not_legal_advice"] is True
    assert body["sources"], "every answer must carry sources"


def test_ask_in_scope_cites_art_12(client: TestClient) -> None:
    resp = client.post(
        "/ask", json={"question": "O fornecedor responde por defeito do produto?", "top_k": 3}
    )
    body = resp.json()
    assert body["status"] == "answered"
    cited = {c for b in body["legal_basis"] for c in b["citations"]}
    assert "cdc-8078-1990-art-12" in cited


def test_ask_out_of_scope_refuses(client: TestClient) -> None:
    # AD-2: the HTTP route must refuse out-of-scope questions via the agentic
    # graph's scope classifier instead of falling back to an unrelated CDC
    # súmula (e.g. STJ Súmula 297) on a tax question. The graph path also
    # guarantees an empty sources/case_law block — nothing recovered, nothing
    # cited.
    resp = client.post(
        "/ask",
        json={"question": "Qual a alíquota do imposto de renda sobre criptomoedas?", "top_k": 3},
    )
    body = resp.json()
    assert body["status"] == "refused"
    assert body["legal_basis"] == []
    assert body["case_law"] == []
    assert body["sources"] == []
    assert body["not_legal_advice"] is True


def test_ask_never_cites_outside_context(client: TestClient) -> None:
    resp = client.post("/ask", json={"question": "defeito do produto", "top_k": 3})
    body = resp.json()
    source_ids = {s["chunk_id"] for s in body["sources"]}
    cited = {c for b in body["legal_basis"] for c in b["citations"]}
    assert cited <= source_ids


def test_ask_returns_separated_case_law_block(client: TestClient) -> None:
    # (a) Consumer question with relevant jurisprudence -> case_law block, with source,
    # separated from legal_basis (legislation).
    resp = client.post(
        "/ask",
        json={"question": "O CDC se aplica a banco e instituição financeira?", "top_k": 5},
    )
    body = resp.json()
    assert body["status"] == "answered"
    case_ids = {c["chunk_id"] for c in body["case_law"]}
    assert "stj-sumula-297" in case_ids
    sumula = next(c for c in body["case_law"] if c["chunk_id"] == "stj-sumula-297")
    assert sumula["court"] == "STJ"
    assert sumula["source_url"]
    cited = {c for b in body["legal_basis"] for c in b["citations"]}
    assert not any(cid.startswith("stj-sumula") for cid in cited)


def test_ask_no_case_law_when_irrelevant(client: TestClient) -> None:
    # (b) Statute-only question -> no jurisprudence block, nothing invented.
    resp = client.post(
        "/ask", json={"question": "O fornecedor responde por defeito do produto?", "top_k": 3}
    )
    body = resp.json()
    assert body["status"] == "answered"
    assert body["case_law"] == []


def test_ask_rejects_empty_question(client: TestClient) -> None:
    resp = client.post("/ask", json={"question": "", "top_k": 3})
    assert resp.status_code == 422
