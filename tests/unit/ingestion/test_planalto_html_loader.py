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


# --- Regression: thousands-separator article numbers (CC art. 1.000+) ---------
# Planalto writes 4-digit articles with a thousands dot ("Art. 1.000.",
# "Art. 1.711.") and, inconsistently, sometimes without ("Art. 1337."). The
# original `\d+` capture truncated "Art. 1.000" to article "1", so the whole
# CC Família/Sucessões range (arts. 1.000–2.046) was lost. These tests pin the
# fix: dotted numbers parse fully, ids are dotless, display keeps the dot.

_THOUSANDS_HTML = """\
<html><body>
<p style="text-align: justify"><font>&nbsp;&nbsp;Art. 999. Texto novecentos.</font></p>
<p style="text-align: justify"><font>&nbsp;&nbsp;Art. 1.000. Texto mil.</font></p>
<p style="text-align: justify"><font>&nbsp;&nbsp;Art. 1.711. Texto bem de familia.</font></p>
<p style="text-align: justify"><font>&nbsp;&nbsp;Art. 1337. Texto sem ponto.</font></p>
<p style="text-align: justify"><font>&nbsp;&nbsp;Art. 2.046. Texto final.</font></p>
</body></html>
""".encode("iso-8859-1")


def test_thousands_separator_articles_are_captured(tmp_path: Path) -> None:
    html_path = tmp_path / "cc.html"
    html_path.write_bytes(_THOUSANDS_HTML)
    seed_path = tmp_path / "cc.md"
    seed_path.write_text(build_seed_markdown(html_path), encoding="utf-8")

    raw = LocalMarkdownLoader(seed_path).load()
    chunks = chunk_document(raw)

    match_tokens = {c.article for c in chunks}
    ids = {c.chunk_id for c in chunks}
    # The `article` field is the dotless match token (so ranking/filter, which
    # compares dotless, matches these high articles). Both source spellings of
    # the same number ("1.337" and "1337") converge to one token "1337".
    assert {"999", "1000", "1711", "1337", "2046"} <= match_tokens
    assert any(cid.endswith("art-1000") for cid in ids)
    assert any(cid.endswith("art-2046") for cid in ids)
    # The human-readable citation surface keeps the thousands dot in `text`.
    text_by_token = {c.article: c.text for c in chunks}
    assert "## Art. 1.000" in text_by_token["1000"]
    assert "## Art. 2.046" in text_by_token["2046"]
    # No article was truncated to its leading digit (the bug): "1" must not
    # appear as an article when the source had no plain "Art. 1".
    assert "1" not in match_tokens
    assert "1º" not in match_tokens


# --- Regression: capital "O" opening a caput is not eaten by the ordinal -------
# The ordinal suffix `[º°o]?` under IGNORECASE used to swallow the uppercase "O"
# that starts many capute bodies ("Art. 10. O fornecedor..." -> "fornecedor..."),
# silently corrupting persisted legal text. The fix accepts only real ordinal
# glyphs (º/°) and the case-sensitive ASCII "o" (the "1o" ordinal).
_LEADING_O_HTML = """\
<html><body>
<p><font>&nbsp;&nbsp;Art. 10. O fornecedor responde pelo defeito.</font></p>
<p><font>&nbsp;&nbsp;Art. 1o Esta lei entra em vigor.</font></p>
<p><font>&nbsp;&nbsp;Art. 5-A. O produto deve ser seguro.</font></p>
<p><font>&nbsp;&nbsp;Art. 12&ordm; Os direitos sao assegurados.</font></p>
</body></html>
""".encode("iso-8859-1")


def test_leading_capital_o_is_preserved_in_caput() -> None:
    md = html_to_markdown(_LEADING_O_HTML)
    # The capital "O" opening the caput survives (BUG 1 regression guard).
    assert "O fornecedor responde pelo defeito." in md
    assert "O produto deve ser seguro." in md
    # The real "1o" ASCII ordinal is consumed, body text intact.
    assert "Esta lei entra em vigor." in md
    assert "1o Esta lei" not in md
    # The º ordinal glyph is consumed; the capital "Os" of the body survives.
    assert "Os direitos sao assegurados." in md


def test_leading_capital_o_preserved_through_chunk(tmp_path: Path) -> None:
    """The capital "O" survives end-to-end into the chunk text (BUG 1 guard)."""
    html_path = tmp_path / "x.html"
    html_path.write_bytes(_LEADING_O_HTML)
    seed_path = tmp_path / "x.md"
    seed_path.write_text(build_seed_markdown(html_path), encoding="utf-8")

    raw = LocalMarkdownLoader(seed_path).load()
    chunks = chunk_document(raw)
    text_by_article = {c.article: c.text for c in chunks}
    assert "O fornecedor responde pelo defeito." in text_by_article["10"]
    # "Art. 5-A" renders the ordinal before the suffix and keeps the caput "O".
    assert "5º-A" in text_by_article
    assert "O produto deve ser seguro." in text_by_article["5º-A"]
