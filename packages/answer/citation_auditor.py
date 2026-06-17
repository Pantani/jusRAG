"""CitationAuditor — audits whether an answer is supported by the retrieved sources (§31).

This is where the inviolable safety rules (§2.1, §2.2, §40) become code. The auditor
re-extracts the *legal claims* from a draft answer (statements that reference an
article, law, right, súmula or thesis), and checks each claim against the recovered
context chunks. A claim is supported when it overlaps sufficiently with some context
chunk *and* every article number it cites actually appears in a context chunk — so a
hallucinated article (e.g. citing "art. 99" never recovered) is flagged even if the
surrounding wording overlaps.

Output is the exact §31 shape::

    {citation_coverage, unsupported_legal_claim_rate, unsupported_claims, passed}

``citation_coverage`` is the fraction of legal claims with support;
``unsupported_legal_claim_rate`` is the complementary fraction. ``passed`` follows the
v1 quality gate (§36): ``unsupported_legal_claim_rate <= 0.05``. The auditor only
*measures*; the AnswerWriter consumes the result to rewrite/refuse (§21).

No LLM, no network — pure, deterministic lexical analysis so unit tests and evals run
offline (system rule §8). The eval-agent reuses :func:`audit_claims` and the
``CitationAuditResult`` metrics directly.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# v1 quality gate (§36): at most 5% of legal claims may be unsupported.
MAX_UNSUPPORTED_LEGAL_CLAIM_RATE = 0.05

# Minimum token-overlap (Jaccard) between a claim and a context chunk to count the
# claim's wording as grounded. Conservative: a claim must share a real chunk of its
# meaningful vocabulary with some recovered source, not a stray word.
_MIN_OVERLAP = 0.18

_SENTENCE_SPLIT = re.compile(r"(?<=[.;:])\s+|\n+")
_WORD = re.compile(r"[0-9a-zãáâàéêíóôõúüçñ]+", re.IGNORECASE)
_ARTICLE_REF = re.compile(r"\bart(?:igo|\.|\b)\.?\s*(\d+)", re.IGNORECASE)
# Súmula / enunciado number, so a hallucinated precedent ("Súmula 999" never
# recovered) is flagged just like a hallucinated article (§2.1).
_SUMULA_REF = re.compile(r"\bs[uú]mula[\s\-]*(?:n[º°.]?\s*)?(\d+)", re.IGNORECASE)

# Legal abbreviations whose trailing dot must NOT be treated as a sentence end.
# Protected with a placeholder before splitting and restored after.
_ABBREV = re.compile(r"\b(art|arts|inc|par|al|n|nº|no)\.", re.IGNORECASE)
_DOT_PLACEHOLDER = "\x00"


def _split_sentences(text: str) -> list[str]:
    """Sentence-split, treating legal abbreviations (``art.``) as mid-sentence."""

    protected = _ABBREV.sub(lambda m: f"{m.group(1)}{_DOT_PLACEHOLDER}", text)
    parts = _SENTENCE_SPLIT.split(protected)
    return [p.replace(_DOT_PLACEHOLDER, ".").strip() for p in parts if p.strip()]

# Markers that make a sentence a *legal* claim worth auditing. Anything that asserts
# a norm, a right, or a legal consequence referencing the legislation.
_LEGAL_MARKERS = frozenset(
    {
        "art",
        "artigo",
        "lei",
        "codigo",
        "cdc",
        "sumula",
        "decreto",
        "constituicao",
        "direito",
        "responde",
        "responsabilidade",
        "fornecedor",
        "consumidor",
        "prazo",
        "garantia",
        "vicio",
        "defeito",
        "indenizacao",
        "obrigacao",
        "nulidade",
        "abusiva",
    }
)

# Short function words that carry no grounding signal.
_STOPWORDS = frozenset(
    {
        "a", "o", "as", "os", "um", "uma", "de", "do", "da", "dos", "das", "e", "ou",
        "que", "com", "sem", "por", "para", "no", "na", "nos", "nas", "em", "ao", "aos",
        "se", "sua", "seu", "suas", "seus", "este", "esta", "esse", "essa", "isto",
        "como", "mais", "menos", "ser", "sao", "foi", "tem", "ter", "ja", "nao", "sim",
        "segundo", "base", "conforme", "ainda", "entre", "sobre", "pode", "deve",
    }
)


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _tokens(text: str) -> set[str]:
    """Meaningful, accent-folded word tokens (drops stopwords and 1-char noise)."""

    folded = _strip_accents(text).lower()
    return {
        w
        for w in _WORD.findall(folded)
        if len(w) > 1 and w not in _STOPWORDS
    }


def _article_refs(text: str) -> set[str]:
    return set(_ARTICLE_REF.findall(_strip_accents(text)))


def _sumula_refs(text: str) -> set[str]:
    return set(_SUMULA_REF.findall(text))


@dataclass(frozen=True)
class AuditChunk:
    """The minimal view of a context source the auditor needs."""

    chunk_id: str
    text: str


@dataclass(frozen=True)
class LegalClaim:
    """A single auditable legal statement extracted from the answer."""

    text: str
    cited_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CitationAuditResult:
    """Audit output in the exact §31 shape."""

    citation_coverage: float
    unsupported_legal_claim_rate: float
    unsupported_claims: list[str] = field(default_factory=list)
    passed: bool = True

    def as_dict(self) -> dict[str, object]:
        return {
            "citation_coverage": self.citation_coverage,
            "unsupported_legal_claim_rate": self.unsupported_legal_claim_rate,
            "unsupported_claims": list(self.unsupported_claims),
            "passed": self.passed,
        }


def _is_legal_claim(claim_tokens: set[str], raw: str) -> bool:
    if _article_refs(raw):
        return True
    return bool(claim_tokens & _LEGAL_MARKERS)


def extract_claims(
    short_answer: str,
    legal_basis: list[LegalClaim],
) -> list[LegalClaim]:
    """Split the answer into auditable *legal* claims.

    Each ``legal_basis`` item is one claim (it already carries its cited chunk ids).
    The ``short_answer`` is sentence-split and only sentences that read as legal
    assertions (cite an article or use a legal marker) are kept.
    """

    claims: list[LegalClaim] = list(legal_basis)
    for sentence in _split_sentences(short_answer):
        if _is_legal_claim(_tokens(sentence), sentence):
            claims.append(LegalClaim(text=sentence))
    return claims


def _overlap(claim_tokens: set[str], chunk_tokens: set[str]) -> float:
    if not claim_tokens:
        return 0.0
    return len(claim_tokens & chunk_tokens) / len(claim_tokens)


def _chunk_articles(chunk: AuditChunk) -> set[str]:
    return _article_refs(chunk.text) | _article_refs(chunk.chunk_id)


def _chunk_sumulas(chunk: AuditChunk) -> set[str]:
    return _sumula_refs(chunk.text) | _sumula_refs(chunk.chunk_id)


def _grounds(claim: LegalClaim, chunk: AuditChunk, claim_tokens: set[str]) -> bool:
    """True iff ``chunk`` grounds the claim's articles, súmulas, and wording.

    Every article number AND súmula number the claim asserts must appear in the
    grounding chunk; a precedent cited but never recovered (hallucinated súmula) is
    flagged even when the surrounding wording overlaps (§2.1, §31).
    """

    claim_articles = _article_refs(claim.text)
    if claim_articles and not claim_articles <= _chunk_articles(chunk):
        return False
    claim_sumulas = _sumula_refs(claim.text)
    if claim_sumulas and not claim_sumulas <= _chunk_sumulas(chunk):
        return False
    return _overlap(claim_tokens, _tokens(chunk.text)) >= _MIN_OVERLAP


def _claim_is_supported(claim: LegalClaim, chunks: list[AuditChunk]) -> bool:
    """A claim is supported iff some chunk grounds both its wording and its articles.

    When the claim carries explicit citations, only those chunks may ground it — so a
    citation pointing at the wrong/absent chunk cannot be rescued by another source.
    Every article number the claim cites must appear in the grounding chunk, so a
    hallucinated article (never recovered) is always flagged.
    """

    claim_tokens = _tokens(claim.text)
    cited = set(claim.cited_ids)
    candidates = [c for c in chunks if not cited or c.chunk_id in cited]
    return any(_grounds(claim, chunk, claim_tokens) for chunk in candidates)


def audit_claims(
    short_answer: str,
    legal_basis: list[LegalClaim],
    chunks: list[AuditChunk],
    *,
    max_unsupported_rate: float = MAX_UNSUPPORTED_LEGAL_CLAIM_RATE,
) -> CitationAuditResult:
    """Audit an answer's legal claims against the recovered context (§31).

    Returns the §31 metrics. An answer with no auditable legal claim is vacuously
    fully covered (coverage 1.0) — there is nothing unsupported to flag.
    """

    claims = extract_claims(short_answer, legal_basis)
    if not claims:
        return CitationAuditResult(
            citation_coverage=1.0,
            unsupported_legal_claim_rate=0.0,
            unsupported_claims=[],
            passed=True,
        )

    unsupported = [c.text for c in claims if not _claim_is_supported(c, chunks)]
    total = len(claims)
    unsupported_rate = len(unsupported) / total
    coverage = 1.0 - unsupported_rate
    return CitationAuditResult(
        citation_coverage=coverage,
        unsupported_legal_claim_rate=unsupported_rate,
        unsupported_claims=unsupported,
        passed=unsupported_rate <= max_unsupported_rate,
    )
