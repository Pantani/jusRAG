"""Integration: POST /search via TestClient, offline (fake provider + memory store).

Overrides the real OpenAI/Qdrant dependencies with the deterministic fake provider
and in-memory store, so no network or running Qdrant is needed (system rule §8).
Proves the §19 acceptance: defeito -> art. 12, arrependimento -> art. 49, with
score + citation metadata in the response.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import get_embedding_provider, get_vector_store
from apps.api.main import create_app
from packages.embeddings.fake_provider import FakeEmbeddingProvider
from packages.legal_types.enums import DocType, LegalArea, Source
from packages.legal_types.schemas import LegalChunk
from packages.storage.memory import InMemoryVectorStore

_SEED = {
    "12": "## Art. 12\n\nO fabricante e o importador respondem por defeitos do produto.",
    "18": "## Art. 18\n\nOs fornecedores respondem pelos vícios de qualidade dos produtos.",
    "49": "## Art. 49\n\nO consumidor pode desistir do contrato, exercendo o direito de "
    "arrependimento, no prazo de sete dias.",
}

_CASE_LAW_SEED = {
    "297": "O Código de Defesa do Consumidor é aplicável às instituições financeiras.",
}

_BANK_QUERY = "CDC aplica-se a banco e instituição financeira"


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
        metadata={"is_current": True, "court": "STJ", "precedent_type": "summary"},
    )


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


@pytest.fixture
def client() -> Iterator[TestClient]:
    provider = FakeEmbeddingProvider()
    store = InMemoryVectorStore()
    chunks = [_chunk(a, t) for a, t in _SEED.items()]
    chunks += [_case_law_chunk(n, e) for n, e in _CASE_LAW_SEED.items()]
    store.upsert_chunks(chunks, provider.embed_texts([c.text for c in chunks]))

    app = create_app()
    app.dependency_overrides[get_embedding_provider] = lambda: provider
    app.dependency_overrides[get_vector_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_search_defeito_returns_art_12(client: TestClient) -> None:
    resp = client.post("/search", json={"query": "defeito do produto", "top_k": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"][0]["citation"]["article"] == "12"


def test_search_arrependimento_returns_art_49(client: TestClient) -> None:
    resp = client.post("/search", json={"query": "direito de arrependimento", "top_k": 3})
    assert resp.status_code == 200
    assert resp.json()["results"][0]["citation"]["article"] == "49"


def test_search_response_carries_score_and_metadata(client: TestClient) -> None:
    resp = client.post("/search", json={"query": "defeito do produto", "top_k": 1})
    hit = resp.json()["results"][0]
    assert hit["score"] > 0
    assert hit["semantic_score"] >= 0
    assert hit["citation"]["chunk_id"] == "cdc-8078-1990-art-12"
    assert hit["citation"]["source_url"]
    assert "## Art. 12" in hit["text"]


def test_search_filter_case_law_returns_only_case_law(client: TestClient) -> None:
    resp = client.post(
        "/search",
        json={"query": _BANK_QUERY, "top_k": 5, "filters": {"doc_type": "case_law"}},
    )
    results = resp.json()["results"]
    assert results, "STJ súmula should be retrievable for a banking query"
    assert all(r["citation"]["doc_type"] == "case_law" for r in results)
    assert results[0]["chunk_id"] == "stj-sumula-297"


def test_search_filter_statute_excludes_case_law(client: TestClient) -> None:
    resp = client.post(
        "/search",
        json={"query": "defeito do produto", "top_k": 5, "filters": {"doc_type": "statute"}},
    )
    results = resp.json()["results"]
    assert all(r["citation"]["doc_type"] == "statute" for r in results)
    assert all(not r["chunk_id"].startswith("stj-sumula") for r in results)
    assert results[0]["citation"]["article"] == "12"


def test_search_separated_blocks(client: TestClient) -> None:
    resp = client.post("/search", json={"query": _BANK_QUERY, "top_k": 5, "separate": True})
    body = resp.json()
    sep = body["separated"]
    assert sep is not None
    assert all(h["citation"]["doc_type"] == "statute" for h in sep["statutes"])
    assert all(h["citation"]["doc_type"] == "case_law" for h in sep["case_law"])
    assert "stj-sumula-297" in {h["chunk_id"] for h in sep["case_law"]}


def test_search_rejects_empty_query(client: TestClient) -> None:
    resp = client.post("/search", json={"query": "", "top_k": 3})
    assert resp.status_code == 422
