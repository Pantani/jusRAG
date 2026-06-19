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
# Article number may carry a thousands separator on Planalto ("Art. 1.000.",
# "Art. 1.711.") and an optional letter suffix ("Art. 1.240-A"). We capture the
# full numeric run *with* its dots and strip them in _format_article_line, so a
# 4-digit article is never truncated to its leading digit (root cause of the CC
# parser stopping at ~art. 999 and losing Família/Sucessões).
# The optional ordinal suffix must NOT swallow the capital "O" that opens many
# capute bodies ("Art. 10. O fornecedor..."). With ``re.IGNORECASE`` a bare
# ``[º°o]?`` matched that "O" and silently dropped it. We accept only the real
# ordinal glyphs ``º``/``°`` plus a *case-sensitive* lowercase ``o`` (the "1o"
# ASCII ordinal) via ``(?-i:o)`` — never the uppercase "O" of a sentence start.
# A single trailing ``.`` after the number/ordinal ("Art. 10.") is consumed too.
_ARTICLE_RE = re.compile(
    r"^\s*Art\.?\s*(\d(?:[\d.]*\d)?(?:-[A-Z])?)(?:[º°]|(?-i:o))?\.?\s*(.*)",
    re.IGNORECASE,
)
# Some Planalto pages (e.g. CTN) split the article marker and its number across
# a <br>: "Art.\n1º Esta Lei...". Join "Art." + newline + digit back so the
# article heading is detected instead of being swallowed as body (no content loss).
_ART_LINEBREAK_RE = re.compile(r"^(\s*Art\.?)\s*\n\s*(\d)", re.IGNORECASE)
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

    # Preserve the source's thousands separator in the heading ("Art. 1.000")
    # for citation fidelity; the chunker strips it only for the id, never for
    # display or body text.
    stem, sep, suffix = num.partition("-")
    base = stem.replace(".", "")
    if base.isdigit() and int(base) < 10:
        # Ordinal mark before the letter suffix: "1-A" -> "1º-A", never "1-Aº".
        token = f"{stem}º-{suffix}" if sep else f"{stem}º"
    else:
        token = num
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
        text = _ART_LINEBREAK_RE.sub(r"\1 \2", _clean_inline(para.text))
        if not text:
            continue
        if para.centered:
            _emit_centered(lines, text)
            continue
        # The Planalto HTML sometimes packs the article heading and a multi-line
        # caput into a single ``<p>``. ``_ARTICLE_RE`` only matches the first
        # line, so split off any remaining lines and emit them as body so the
        # full caput reaches the chunk (was silently truncated before).
        first_line, _, remainder = text.partition("\n")
        art_match = _ARTICLE_RE.match(first_line)
        if art_match:
            _emit_article(lines, art_match)
            in_article = True
            remainder = remainder.strip()
            if remainder:
                _emit_article_body(lines, remainder)
            continue
        if not in_article:
            # Preamble lines stay above the first article (chunker skips them).
            lines.append(text)
            continue
        _emit_article_body(lines, text)

    return _collapse_blank_runs(lines)


# ---------- Public entrypoint ----------


@dataclass(frozen=True, slots=True)
class SeedSpec:
    """Provenance descriptor that parametrizes the seed-markdown frontmatter.

    Lets the deterministic HTML->markdown converter serve any Planalto-vendored
    federal code (CDC, CF/88, CC, CP, CLT, CTN, CPC, CPP), not just the CDC. The
    body conversion stays identical; only the frontmatter (consumed by
    ``LocalMarkdownLoader``) changes per code. ``source_html_rel`` is the repo
    path of the vendored HTML, embedded for auditability (§2/§40.4).
    """

    short_name: str
    title: str
    source_url: str
    norm_type: str
    norm_number: str
    norm_year: str
    legal_area: str
    source_html_rel: str
    version: str = "compilado"
    jurisdiction: str = "federal"
    source: str = "planalto"


_CDC_SPEC = SeedSpec(
    short_name="cdc",
    title="Código de Defesa do Consumidor (Lei nº 8.078/1990)",
    source_url="https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm",
    norm_type="lei",
    norm_number="8078",
    norm_year="1990",
    legal_area="consumer",
    source_html_rel="data/seed/cdc/_source/planalto_l8078compilado.html",
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


def build_seed_markdown(html_path: Path, spec: SeedSpec | None = None) -> str:
    """Build a seed markdown (frontmatter + body) from a vendored HTML file.

    ``spec`` selects the code's provenance frontmatter; it defaults to the CDC
    (backward-compatible with the Phase-13 ``ingest_cdc`` flow). Idempotent:
    invoking twice on the same bytes returns byte-identical text. No timestamp
    inside the output — provenance is pinned by ``fonte_html_hash``.
    """

    spec = spec or _CDC_SPEC
    html_bytes = html_path.read_bytes()
    body = html_to_markdown(html_bytes)
    fonte_hash = hashlib.sha256(html_bytes).hexdigest()

    frontmatter = (
        "<!--\n"
        f"short_name: {spec.short_name}\n"
        f"title: {spec.title}\n"
        f"source: {spec.source}\n"
        f"source_url: {spec.source_url}\n"
        f"norm_type: {spec.norm_type}\n"
        f"norm_number: {spec.norm_number}\n"
        f"norm_year: {spec.norm_year}\n"
        f"version: {spec.version}\n"
        f"legal_area: {spec.legal_area}\n"
        f"jurisdiction: {spec.jurisdiction}\n"
        f"fonte_html_hash: {fonte_hash}\n"
        "-->\n\n"
        f"# {spec.title}\n\n"
        f"Fonte: Planalto — {spec.source_url}\n"
        f"SHA256 do HTML fonte: {fonte_hash}\n\n"
        "Texto integral gerado deterministicamente a partir do HTML vendored em\n"
        f"`{spec.source_html_rel}`. Conversão sem\n"
        "interpretação: o loader apenas reformata a estrutura (§40.4).\n\n"
    )
    return frontmatter + body
