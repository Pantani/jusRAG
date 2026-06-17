"""Shared fixtures for retrieval-layer unit tests (offline, no network)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.legal_types.enums import DocType, LegalArea, Source
from packages.legal_types.schemas import LegalChunk

# Minimal, self-contained CDC-like chunks mirroring the seed contract:
# chunk.text INCLUDES the "## Art. N" heading; granularity = article.
_SEED = {
    "12": (
        "## Art. 12\n\nO fabricante e o importador respondem, independentemente de culpa, "
        "pela reparação dos danos causados por defeitos do produto."
    ),
    "18": (
        "## Art. 18\n\nOs fornecedores respondem pelos vícios de qualidade que tornem os "
        "produtos impróprios ao consumo."
    ),
    "26": (
        "## Art. 26\n\nO direito de reclamar pelos vícios aparentes caduca; é o prazo "
        "decadencial para reclamar."
    ),
    "49": (
        "## Art. 49\n\nO consumidor pode desistir do contrato no prazo de sete dias, exercendo o "
        "direito de arrependimento, quando a compra ocorrer fora do estabelecimento comercial."
    ),
}


def _chunk(article: str, text: str) -> LegalChunk:
    return LegalChunk(
        chunk_id=f"cdc-8078-1990-art-{article}",
        document_id="cdc-8078-1990",
        doc_type=DocType.STATUTE,
        source=Source.PLANALTO,
        title="Código de Defesa do Consumidor (Lei nº 8.078/1990)",
        legal_area=LegalArea.CONSUMER,
        jurisdiction="federal",
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
def cdc_chunks() -> list[LegalChunk]:
    return [_chunk(article, text) for article, text in _SEED.items()]


def _case_law_chunk(number: str, ementa: str) -> LegalChunk:
    """STJ súmula chunk (doc_type=case_law) mirroring the §9 case-law payload.

    Precedent metadata travels in ``metadata`` (court, precedent_type, ...), as
    produced by the ingestion chunker — so ranking can resolve the STJ-súmula
    authority tier (0.88) from the stored payload.
    """

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


_CASE_LAW_SEED = {
    "297": "O Código de Defesa do Consumidor é aplicável às instituições financeiras.",
    "479": (
        "As instituições financeiras respondem objetivamente pelos danos gerados por "
        "fortuito interno relativo a fraudes e delitos praticados por terceiros no "
        "âmbito de operações bancárias."
    ),
}


@pytest.fixture
def case_law_chunks() -> list[LegalChunk]:
    return [_case_law_chunk(n, e) for n, e in _CASE_LAW_SEED.items()]
