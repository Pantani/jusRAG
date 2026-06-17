"""Determinism and conservatism of `normalize_text`."""

from __future__ import annotations

from packages.ingestion.normalizer import normalize_text


def test_idempotent() -> None:
    text = "Art. 12\n\n\n  O fornecedor   responde\r\n  pelos danos."
    once = normalize_text(text)
    assert normalize_text(once) == once


def test_deterministic_same_input_same_output() -> None:
    text = "  linha  com   espaços \t extra  "
    assert normalize_text(text) == normalize_text(text)


def test_crlf_and_nbsp_normalized() -> None:
    assert normalize_text("a\r\nb") == "a\nb"
    assert normalize_text("a b") == "a b"


def test_collapses_blank_lines_and_trims() -> None:
    out = normalize_text("\n\nfirst\n\n\n\nsecond  \n\n")
    assert out == "first\n\nsecond"


def test_preserves_legal_wording() -> None:
    text = "O fornecedor responde, independentemente de culpa."
    assert normalize_text(text) == text
