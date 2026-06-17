"""Deterministic text normalization (§8, §12.3).

Normalization runs *before* hashing. It must be deterministic: the same input
always yields the same output, otherwise hash-level idempotency breaks. We keep
it conservative — we do not mutate legal wording, only whitespace/extraction
noise — so the normalized text stays faithful to the source.
"""

from __future__ import annotations

import re
import unicodedata

_NBSP = " "
_TRAILING_WS = re.compile(r"[ \t]+(?=\n)")
_INTRALINE_WS = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    """Return a canonical form of ``text`` suitable for hashing.

    Steps (all deterministic):
    - Unicode NFC normalization;
    - CRLF/CR -> LF;
    - non-breaking spaces -> regular spaces;
    - collapse runs of intra-line whitespace to a single space;
    - strip trailing whitespace per line;
    - collapse 3+ blank lines to a single blank line;
    - strip leading/trailing blank lines.
    """

    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(_NBSP, " ")
    text = _INTRALINE_WS.sub(" ", text)
    text = _TRAILING_WS.sub("", text)
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip("\n").strip()
