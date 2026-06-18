"""Multi-area retrieval: the ``legal_area`` filter must isolate areas (§9/§28).

Offline, no network: ``FakeEmbeddingProvider`` + ``InMemoryVectorStore`` over a
tiny civil/criminal corpus. Filtering ``civil`` must never surface a ``criminal``
chunk, and vice-versa — the cross-area corpus shares the single ``legal_chunks``
collection, so isolation is enforced purely by the metadata filter.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.embeddings.fake_provider import FakeEmbeddingProvider
from packages.legal_types.enums import DocType, LegalArea, Source
from packages.legal_types.schemas import LegalChunk
from packages.rag.retriever import LegalRetriever
from packages.rag.types import RetrievalQuery
from packages.storage.memory import InMemoryVectorStore


def _statute(*, area: LegalArea, norm_type: str, article: str, text: str) -> LegalChunk:
    return LegalChunk(
        chunk_id=f"{area.value}-{article}",
        document_id=f"{area.value}-doc",
        doc_type=DocType.STATUTE,
        source=Source.PLANALTO,
        title=f"{area.value} code",
        legal_area=area,
        jurisdiction="federal",
        norm_type=norm_type,
        norm_number="0",
        norm_year="2000",
        article=article,
        text=text,
        source_url="https://www.planalto.gov.br/x",
        version="2026-06-18",
        content_hash=f"sha256:fixture-{area.value}-{article}",
        created_at=datetime(2026, 6, 18, tzinfo=UTC),
        metadata={"is_current": True},
    )


_CORPUS = [
    _statute(
        area=LegalArea.CIVIL,
        norm_type="lei",
        article="186",
        text="## Art. 186\n\nAquele que por ação ou omissão voluntária causar dano a outrem "
        "comete ato ilícito e fica obrigado a reparar o dano civil.",
    ),
    _statute(
        area=LegalArea.CRIMINAL,
        norm_type="decreto_lei",
        article="121",
        text="## Art. 121\n\nMatar alguém: pena de reclusão. Homicídio é crime contra a vida "
        "tipificado no Código Penal, dano e ato ilícito penal.",
    ),
]


@pytest.fixture
def retriever() -> LegalRetriever:
    provider = FakeEmbeddingProvider()
    store = InMemoryVectorStore()
    store.upsert_chunks(_CORPUS, provider.embed_texts([c.text for c in _CORPUS]))
    return LegalRetriever(provider, store)


def test_civil_filter_excludes_criminal(retriever: LegalRetriever) -> None:
    hits = retriever.retrieve(
        RetrievalQuery(query="dano e ato ilícito", top_k=5, legal_area="civil")
    )
    ids = {h.chunk_id for h in hits}
    assert ids == {"civil-186"}


def test_criminal_filter_excludes_civil(retriever: LegalRetriever) -> None:
    hits = retriever.retrieve(
        RetrievalQuery(query="dano e ato ilícito", top_k=5, legal_area="criminal")
    )
    ids = {h.chunk_id for h in hits}
    assert ids == {"criminal-121"}


def test_no_area_filter_returns_both(retriever: LegalRetriever) -> None:
    hits = retriever.retrieve(RetrievalQuery(query="dano e ato ilícito", top_k=5))
    ids = {h.chunk_id for h in hits}
    assert {"civil-186", "criminal-121"} <= ids
