"""Planalto HTML -> seed markdown converter (§12.3, §40.4).

Reads a vendored copy of a Planalto-compiled law page (e.g.
``l8078compilado.htm``) and produces the structured markdown the chunker
already consumes (``## Art. N`` per article, with paragraphs/incisos/alíneas
preserved).

Design constraints:

- **Determinístico**: same input bytes -> byte-identical markdown. No timestamps
  embedded inside the converted body; the only date-like field in the
  frontmatter is the Planalto-published source version when we can detect it
  (otherwise the fixed string ``compilado``).
- **Fonte auditável (§2)**: nothing is invented. The conversion is a structural
  reformat of the bytes on disk under ``data/seed/cdc/_source/``; the
  ``fonte_html_hash`` field in the frontmatter pins the exact source version.
- **Stdlib only**: uses ``html.parser`` — no new dependency.
- **Loader boundary (§12.9)**: this module writes markdown to disk; chunking
  and embeddings remain downstream.

The output frontmatter mirrors the existing ``LocalMarkdownLoader`` schema so
the rest of the pipeline (`LocalMarkdownLoader` -> `chunk_document`) is reused
unchanged.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

# ---------- HTML -> structured paragraphs ----------


@dataclass(frozen=True, slots=True)
class _Paragraph:
    """A single ``<p>`` extracted from the Planalto HTML."""

    text: str
    centered: bool


class _ParagraphCollector(HTMLParser):
    """Extracts ``<p>`` blocks with a coarse ``centered?`` flag.

    Centered paragraphs in the Planalto layout carry structural headers
    (``TÍTULO``, ``CAPÍTULO``, ``SEÇÃO``, ``SUBSEÇÃO``). Everything else is
    article body content.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[_Paragraph] = []
        self._buf: list[str] | None = None
        self._centered: bool = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "p":
            self._buf = []
            attr_map = {k: (v or "") for k, v in attrs}
            align = attr_map.get("align", "").lower()
            style = attr_map.get("style", "").lower()
            self._centered = align == "center" or "text-align: center" in style
        elif tag == "br" and self._buf is not None:
            self._buf.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self._buf is not None:
            self.paragraphs.append(
                _Paragraph(text="".join(self._buf), centered=self._centered)
            )
            self._buf = None
            self._centered = False

    def handle_data(self, data: str) -> None:
        if self._buf is not None:
            self._buf.append(data)


# ---------- Classification ----------

_HEADER_PREFIXES = ("TÍTULO ", "CAPÍTULO ", "SEÇÃO ", "SUBSEÇÃO ", "LIVRO ")
_ARTICLE_RE = re.compile(r"^\s*Art\.?\s*(\d+(?:-[A-Z])?)\s*[º°o]?\s*(.*)", re.IGNORECASE)
_PARAGRAPH_RE = re.compile(r"^\s*(§\s*\d+\s*[º°o]?|Parágrafo único\.?)", re.IGNORECASE)
_INCISO_RE = re.compile(r"^\s*([IVXLCDM]+)\s*[-–]\s*", re.IGNORECASE)
_ALINEA_RE = re.compile(r"^\s*([a-z])\)\s*", re.IGNORECASE)


def _clean_inline(text: str) -> str:
    """Collapse intra-line whitespace, preserve explicit newlines.

    Removes the leading ``&nbsp;`` indent block used by the Planalto template
    while keeping the actual sentence text intact. Deterministic.
    """

    # Normalize NBSP and other unicode spaces to ASCII space first.
    text = text.replace(" ", " ").replace("​", "")
    # Collapse runs of spaces/tabs but keep newlines.
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _classify_centered(text: str) -> tuple[str, str] | None:
    """Return ``(kind, normalized_text)`` for a structural header, or ``None``.

    ``kind`` is one of ``LIVRO``, ``TITULO``, ``CAPITULO``, ``SECAO``,
    ``SUBSECAO``. Two-line centered blocks (e.g. ``CAPÍTULO I`` + title) are
    joined with an em dash for readability.
    """

    flat = " ".join(text.split())
    upper = flat.upper()
    for prefix in _HEADER_PREFIXES:
        if upper.startswith(prefix):
            kind = (
                prefix.strip()
                .replace("Í", "I")
                .replace("Ç", "C")
                .replace("Ã", "A")
            )
            # Split "CAPÍTULO I Disposições Gerais" -> "CAPÍTULO I — Disposições Gerais".
            tokens = flat.split(" ", 2)
            if len(tokens) >= 3:
                normalized = f"{tokens[0]} {tokens[1]} — {tokens[2]}"
            else:
                normalized = flat
            return kind, normalized
    return None


def _markdown_header_for(kind: str) -> str:
    """Map a structural ``kind`` to a markdown header level above ``##``."""

    return {
        "LIVRO": "#",
        "TITULO": "#",
        "CAPITULO": "#",
        "SECAO": "###",
        "SUBSECAO": "####",
    }.get(kind, "#")


# ---------- Article assembly ----------


def _format_article_line(num: str, rest: str) -> tuple[str, str]:
    """Return ``(article_token, first_body_line)`` for an ``Art. N`` paragraph.

    ``article_token`` is the canonical heading form expected by the chunker
    (``6º`` for single-digit, ``12`` for double-digit, ``42-A`` for composite).
    ``first_body_line`` is the article body text that followed ``Art. N`` on
    the same paragraph (often the article caput).
    """

    base = num.split("-")[0]
    token = f"{num}º" if base.isdigit() and int(base) < 10 else num
    return token, rest.strip()


def _emit_centered(lines: list[str], text: str) -> None:
    """Append a structural header (or skip non-header centered noise)."""

    classified = _classify_centered(text)
    if classified is None:
        return
    kind, normalized = classified
    lines.extend(("", f"{_markdown_header_for(kind)} {normalized}", ""))


def _emit_article(lines: list[str], match: re.Match[str]) -> None:
    """Append a ``## Art. <token>`` heading followed by the caput body."""

    token, body = _format_article_line(match.group(1), match.group(2))
    lines.extend(("", f"## Art. {token}", ""))
    if body:
        lines.append(body)


def _emit_article_body(lines: list[str], text: str) -> None:
    """Append a body paragraph (§/inciso/alínea/free text) under the current article."""

    prefix = "  " if _ALINEA_RE.match(text) else ""
    lines.extend(("", f"{prefix}{text}"))


def _collapse_blank_runs(lines: list[str]) -> str:
    """Collapse consecutive blank lines to at most one; return final text."""

    out: list[str] = []
    prev_blank = False
    for line in lines:
        blank = line == ""
        if blank and prev_blank:
            continue
        out.append(line)
        prev_blank = blank
    return "\n".join(out).strip("\n") + "\n"


def _convert_paragraphs(paragraphs: list[_Paragraph]) -> str:
    """Turn ``<p>`` paragraphs into the structured markdown body.

    Output contract for the downstream chunker:
    - A line ``## Art. <token>`` starts each article.
    - The article caput follows on the next blank-line-separated paragraph.
    - Structural headers (``CAPÍTULO``, etc.) become ``#``/``###``/``####``
      lines and are ignored by the article chunker but help human readers.
    """

    lines: list[str] = []
    in_article = False

    for para in paragraphs:
        text = _clean_inline(para.text)
        if not text:
            continue
        if para.centered:
            _emit_centered(lines, text)
            continue
        in_article = _emit_paragraph(lines, text, in_article=in_article)

    return _collapse_blank_runs(lines)


def _emit_paragraph(lines: list[str], text: str, *, in_article: bool) -> bool:
    """Emit one non-centered paragraph; return the updated ``in_article`` state."""
    # The Planalto HTML sometimes packs the article heading and a multi-line
    # caput into a single ``<p>``. ``_ARTICLE_RE`` only matches the first line,
    # so split off any remaining lines and emit them as body so the full caput
    # reaches the chunk (was silently truncated before).
    first_line, _, remainder = text.partition("\n")
    art_match = _ARTICLE_RE.match(first_line)
    if art_match:
        _emit_article(lines, art_match)
        remainder = remainder.strip()
        if remainder:
            _emit_article_body(lines, remainder)
        return True
    if not in_article:
        # Preamble lines stay above the first article (chunker skips them).
        lines.append(text)
        return in_article
    _emit_article_body(lines, text)
    return in_article


# ---------- Public entrypoint ----------


_PUBLICATION_RE = re.compile(
    r"LEI N[º°]?\s*8\.?078,\s*DE\s*11\s*DE\s*SETEMBRO\s*DE\s*1990", re.IGNORECASE
)


def html_to_markdown(html_bytes: bytes) -> str:
    """Convert Planalto HTML bytes to the seed markdown body (no frontmatter).

    Deterministic and pure. Decoding is ISO-8859-1 — the Planalto pages are
    served in latin-1 and do not declare a charset reliably.
    """

    text = html_bytes.decode("iso-8859-1")
    parser = _ParagraphCollector()
    parser.feed(text)
    return _convert_paragraphs(parser.paragraphs)


def build_seed_markdown(html_path: Path) -> str:
    """Build the full ``cdc.md`` (frontmatter + body) from a vendored HTML file.

    Idempotent: invoking twice on the same bytes returns byte-identical text.
    No timestamp inside the output — provenance is pinned by
    ``fonte_html_hash``.
    """

    html_bytes = html_path.read_bytes()
    body = html_to_markdown(html_bytes)
    fonte_hash = hashlib.sha256(html_bytes).hexdigest()

    frontmatter = (
        "<!--\n"
        "short_name: cdc\n"
        "title: Código de Defesa do Consumidor (Lei nº 8.078/1990)\n"
        "source: planalto\n"
        "source_url: https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm\n"
        "norm_type: lei\n"
        "norm_number: 8078\n"
        "norm_year: 1990\n"
        "version: compilado\n"
        "legal_area: consumer\n"
        "jurisdiction: federal\n"
        f"fonte_html_hash: {fonte_hash}\n"
        "-->\n\n"
        "# Código de Defesa do Consumidor — Lei nº 8.078, de 11 de setembro de 1990\n\n"
        "Fonte: Planalto — https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm\n"
        f"SHA256 do HTML fonte: {fonte_hash}\n\n"
        "Texto integral gerado deterministicamente a partir do HTML vendored em\n"
        "`data/seed/cdc/_source/planalto_l8078compilado.html`. Conversão sem\n"
        "interpretação: o loader apenas reformata a estrutura (§40.4).\n\n"
    )
    return frontmatter + body
