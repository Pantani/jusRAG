"""Registry of the core federal codes vendored from Planalto (§12.3, §40.4).

Each :class:`CodeEntry` binds a vendored HTML source to the provenance metadata
needed to build citable chunks: ``norm_type`` (including ``decreto_lei`` for
CP/CPP/CLT, Phase A), ``legal_area``, ``norm_number``/``norm_year``, and the
official Planalto URL. The ingestion job iterates this registry to produce one
multi-area JSONL of ``LegalChunk``s.

Nothing here invents legal content — the registry only pins *where* each code's
bytes live on disk and *how* to label them. The article text always comes from
the vendored HTML (§2).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from packages.ingestion.loaders.planalto_html import SeedSpec

# Repo root: this file lives at packages/ingestion/codes.py.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SEED = _REPO_ROOT / "data" / "seed"


@dataclass(frozen=True, slots=True)
class CodeEntry:
    """A core federal code: its vendored HTML, seed markdown, and provenance."""

    spec: SeedSpec

    @property
    def source_html(self) -> Path:
        return _REPO_ROOT / self.spec.source_html_rel

    @property
    def seed_markdown(self) -> Path:
        # Sibling of the _source/ dir: data/seed/<code-dir>/<short_name>.md
        return self.source_html.parent.parent / f"{self.spec.short_name}.md"


def _entry(
    *,
    short_name: str,
    title: str,
    url: str,
    norm_type: str,
    norm_number: str,
    norm_year: str,
    legal_area: str,
    html_rel: str,
) -> CodeEntry:
    return CodeEntry(
        SeedSpec(
            short_name=short_name,
            title=title,
            source_url=url,
            norm_type=norm_type,
            norm_number=norm_number,
            norm_year=norm_year,
            legal_area=legal_area,
            source_html_rel=html_rel,
        )
    )


# The 7 core federal codes (Phase B). Order is stable for deterministic output.
CORE_CODES: tuple[CodeEntry, ...] = (
    _entry(
        short_name="cf88",
        title="Constituição da República Federativa do Brasil de 1988",
        url="https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
        norm_type="constituicao",
        norm_number="1988",
        norm_year="1988",
        legal_area="constitutional",
        html_rel="data/seed/constitucional/_source/planalto_constituicao.html",
    ),
    _entry(
        short_name="cc",
        title="Código Civil (Lei nº 10.406/2002)",
        # URL fornecida no escopo (_ato2002-2006/...) retorna 404; a URL
        # canônica do Planalto para o compilado é a abaixo (verificada, HTTP 200).
        url="https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm",
        norm_type="lei",
        norm_number="10406",
        norm_year="2002",
        legal_area="civil",
        html_rel="data/seed/civil_cc/_source/planalto_l10406compilada.html",
    ),
    _entry(
        short_name="cp",
        title="Código Penal (Decreto-Lei nº 2.848/1940)",
        url="https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm",
        norm_type="decreto_lei",
        norm_number="2848",
        norm_year="1940",
        legal_area="criminal",
        html_rel="data/seed/criminal_cp/_source/planalto_del2848compilado.html",
    ),
    _entry(
        short_name="clt",
        title="Consolidação das Leis do Trabalho (Decreto-Lei nº 5.452/1943)",
        url="https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452compilado.htm",
        norm_type="decreto_lei",
        norm_number="5452",
        norm_year="1943",
        legal_area="labor",
        html_rel="data/seed/labor_clt/_source/planalto_del5452compilado.html",
    ),
    _entry(
        short_name="ctn",
        title="Código Tributário Nacional (Lei nº 5.172/1966)",
        url="https://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm",
        norm_type="lei",
        norm_number="5172",
        norm_year="1966",
        legal_area="tax",
        html_rel="data/seed/tax_ctn/_source/planalto_l5172compilado.html",
    ),
    _entry(
        short_name="cpc",
        title="Código de Processo Civil (Lei nº 13.105/2015)",
        url="https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm",
        norm_type="lei",
        norm_number="13105",
        norm_year="2015",
        legal_area="civil",
        html_rel="data/seed/civil_cpc/_source/planalto_l13105.html",
    ),
    _entry(
        short_name="cpp",
        title="Código de Processo Penal (Decreto-Lei nº 3.689/1941)",
        url="https://www.planalto.gov.br/ccivil_03/decreto-lei/del3689compilado.htm",
        norm_type="decreto_lei",
        norm_number="3689",
        norm_year="1941",
        legal_area="criminal",
        html_rel="data/seed/criminal_cpp/_source/planalto_del3689compilado.html",
    ),
)
