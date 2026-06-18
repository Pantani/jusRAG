"""Tests for the Planalto HTML -> markdown seed converter (§12.3, §40.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.ingestion.chunker import chunk_document
from packages.ingestion.loaders.local_markdown import LocalMarkdownLoader
from packages.ingestion.loaders.planalto_html import (
    build_seed_markdown,
    html_to_markdown,
)

# Tiny fixture: 3 articles + a chapter header, hand-crafted to mirror the
# Planalto template (latin-1 + <p> blocks + centered headers + &nbsp; indent).
_FIXTURE_HTML = """\
<html><body>
<p align="center"><font face="Arial">LEI N&ordm; 8.078, DE 11 DE SETEMBRO DE 1990.</font></p>
<p style="text-align: center"><font face="Arial">CAP&Iacute;TULO I<br>
Disposi&ccedil;&otilde;es Gerais</font></p>
<p style="text-align: justify"><font face="Arial">&nbsp;&nbsp;&nbsp;&nbsp;
Art. 1&ordm; O presente c&oacute;digo estabelece normas de prote&ccedil;&atilde;o.</font></p>
<p style="text-align: justify"><font face="Arial">&nbsp;&nbsp;&nbsp;&nbsp;
Art. 2&ordm; Consumidor &eacute; toda pessoa f&iacute;sica ou jur&iacute;dica.</font></p>
<p style="text-align: justify"><font face="Arial">&nbsp;&nbsp;&nbsp;&nbsp;
Par&aacute;grafo &uacute;nico. Equipara-se a consumidor a coletividade.</font></p>
<p style="text-align: justify"><font face="Arial">&nbsp;&nbsp;&nbsp;&nbsp;
Art. 3&ordm; Fornecedor &eacute; toda pessoa.</font></p>
<p style="text-align: justify"><font face="Arial">&nbsp;&nbsp;&nbsp;&nbsp;
&sect; 1&ordm; Produto &eacute; qualquer bem.</font></p>
<p style="text-align: justify"><font face="Arial">&nbsp;&nbsp;&nbsp;&nbsp;
I - primeiro inciso;</font></p>
<p style="text-align: justify"><font face="Arial">&nbsp;&nbsp;&nbsp;&nbsp;
a) primeira al&iacute;nea.</font></p>
</body></html>
""".encode("iso-8859-1")


def test_html_to_markdown_emits_article_headers() -> None:
    md = html_to_markdown(_FIXTURE_HTML)
    assert "## Art. 1º" in md
    assert "## Art. 2º" in md
    assert "## Art. 3º" in md
    # Chapter header is preserved as a level-1 markdown header (above ##).
    assert "# CAPÍTULO I — Disposições Gerais" in md
    # Article body content is preserved.
    assert "O presente código estabelece normas de proteção." in md
    assert "Parágrafo único. Equipara-se a consumidor a coletividade." in md
    assert "§ 1º Produto é qualquer bem." in md
    assert "I - primeiro inciso;" in md
    assert "a) primeira alínea." in md


def test_html_to_markdown_is_deterministic() -> None:
    a = html_to_markdown(_FIXTURE_HTML)
    b = html_to_markdown(_FIXTURE_HTML)
    assert a == b


def test_build_seed_markdown_pins_html_hash(tmp_path: Path) -> None:
    html_path = tmp_path / "src.html"
    html_path.write_bytes(_FIXTURE_HTML)
    md = build_seed_markdown(html_path)
    # Frontmatter is present and references the SHA256 of the source bytes.
    assert md.startswith("<!--\n")
    assert "fonte_html_hash:" in md
    import hashlib

    expected = hashlib.sha256(_FIXTURE_HTML).hexdigest()
    assert expected in md


def test_build_seed_markdown_idempotent(tmp_path: Path) -> None:
    html_path = tmp_path / "src.html"
    html_path.write_bytes(_FIXTURE_HTML)
    assert build_seed_markdown(html_path) == build_seed_markdown(html_path)


def test_generated_markdown_chunks_through_existing_loader(tmp_path: Path) -> None:
    """Round-trip: generated markdown -> LocalMarkdownLoader -> chunker."""
    html_path = tmp_path / "src.html"
    html_path.write_bytes(_FIXTURE_HTML)
    seed_path = tmp_path / "cdc.md"
    seed_path.write_text(build_seed_markdown(html_path), encoding="utf-8")

    raw = LocalMarkdownLoader(seed_path).load()
    chunks = chunk_document(raw)
    articles = sorted(c.article for c in chunks)
    assert articles == ["1º", "2º", "3º"]
    # Each chunk has a non-empty content hash and the right doc identity.
    for c in chunks:
        assert c.content_hash
        assert c.norm_number == "8078"
        assert c.norm_year == "1990"


@pytest.mark.parametrize("which", ["raises_on_missing_file"])
def test_build_seed_markdown_requires_existing_file(tmp_path: Path, which: str) -> None:
    with pytest.raises(FileNotFoundError):
        build_seed_markdown(tmp_path / "does_not_exist.html")
