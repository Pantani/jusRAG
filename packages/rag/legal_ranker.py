"""Composite legal ranking — MVP score (§38).

    score = 0.70 * semantic_similarity
          + 0.20 * legal_authority
          + 0.10 * exact_citation_match

- ``semantic_similarity``: raw cosine from the vector store, clamped to [0, 1].
- ``legal_authority``: authority weight from the §39 hierarchy, looked up from the
  chunk payload (norm_type for statutes; doc_type fallback otherwise).
- ``exact_citation_match``: 1.0 when the article number requested in the query
  matches the chunk's article (chunk text carries the "## Art. N" heading too).

BM25, binding weight, recency and source-quality terms are deferred (§38 full).
"""

from __future__ import annotations

import re

from packages.legal_types.enums import DocType, PrecedentType
from packages.legal_types.hierarchy import (
    _FEDERAL_LAW_NORMS,
    AuthorityTier,
    authority_weight_for_doc_type,
    weight_for,
)
from packages.storage.base import VectorSearchResult

# Phrase-overlap window: minimum consecutive query tokens that must appear
# verbatim in a chunk to award the citation-tier lexical bonus. Conservative
# (4 tokens) so it only fires on genuine quote-like queries — the kind that
# break pure semantic ranking when the citation unit is a long article whose
# semantic centroid drifts away from a specific inciso (e.g. art. 39 CDC).
_PHRASE_WINDOW = 4

# STJ precedent-type tiers (§39): a STJ súmula weighs 0.88, not the generic
# case-law fallback (0.75). Mirrors hierarchy._STJ_PRECEDENT_TIERS but driven
# by the stored payload (precedent_type lives in chunk.metadata for case_law).
_PRECEDENT_TIERS: dict[PrecedentType, AuthorityTier] = {
    PrecedentType.REPETITIVE_APPEAL: AuthorityTier.STJ_REPETITIVE,
    PrecedentType.SUMMARY: AuthorityTier.STJ_SUMMARY,
    PrecedentType.BINDING_SUMMARY: AuthorityTier.FEDERAL_LAW,
    PrecedentType.BINDING_PRECEDENT: AuthorityTier.FEDERAL_LAW,
    PrecedentType.GENERAL_REPERCUSSION: AuthorityTier.FEDERAL_LAW,
}

SEMANTIC_WEIGHT = 0.70
AUTHORITY_WEIGHT = 0.20
CITATION_WEIGHT = 0.10


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def authority_for_payload(payload: dict[str, object]) -> float:
    """Authority weight (§39) from a stored chunk payload."""

    doc_type_raw = str(payload.get("doc_type", DocType.UNKNOWN))
    try:
        doc_type = DocType(doc_type_raw)
    except ValueError:
        return weight_for(AuthorityTier.UNKNOWN)

    if doc_type is DocType.STATUTE:
        # Strict statute tier from norm_type (§39), mirroring
        # hierarchy.tier_for_statute: constituição = top, only the recognised
        # federal-law norm types (_FEDERAL_LAW_NORMS) = federal-law tier, any
        # other/unknown norm (e.g. "portaria") = UNKNOWN — no permissive 0.95.
        norm = str(payload.get("norm_type") or "").lower()
        if norm in {"constituicao", "constituição"}:
            return weight_for(AuthorityTier.CONSTITUTION)
        if norm in _FEDERAL_LAW_NORMS:
            return weight_for(AuthorityTier.FEDERAL_LAW)
        return weight_for(AuthorityTier.UNKNOWN)
    if doc_type is DocType.CASE_LAW:
        return _case_law_authority(payload)
    return authority_weight_for_doc_type(doc_type)


def _case_law_authority(payload: dict[str, object]) -> float:
    """Case-law tier from precedent_type/court in the chunk metadata (§39).

    For case_law chunks the §9 payload (court, precedent_type) travels inside the
    chunk's ``metadata`` sub-dict — so a STJ súmula scores 0.88, not the coarse
    case-law fallback 0.75.
    """

    meta = payload.get("metadata")
    meta = meta if isinstance(meta, dict) else {}
    precedent_raw = str(meta.get("precedent_type") or "")
    try:
        precedent = PrecedentType(precedent_raw)
    except ValueError:
        precedent = PrecedentType.UNKNOWN
    if precedent in _PRECEDENT_TIERS:
        return weight_for(_PRECEDENT_TIERS[precedent])
    court = str(meta.get("court") or "").upper()
    if court == "STF":
        return weight_for(AuthorityTier.FEDERAL_LAW)
    if court == "STJ":
        return weight_for(AuthorityTier.STJ_CASE_LAW)
    if court.startswith("TJ"):
        return weight_for(AuthorityTier.TJ)
    return authority_weight_for_doc_type(DocType.CASE_LAW)


def exact_citation_match(payload: dict[str, object], requested_article: str | None) -> float:
    """1.0 if the requested article equals the chunk's article, else 0.0."""

    if not requested_article:
        return 0.0
    return 1.0 if str(payload.get("article") or "") == str(requested_article) else 0.0


_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(text)]


def phrase_overlap(query: str, chunk_text: str, window: int = _PHRASE_WINDOW) -> float:
    """1.0 when any ``window``-token query n-gram appears verbatim in ``chunk_text``.

    Lexical fallback that complements semantic similarity when the citation unit
    is large (e.g. CDC art. 39, with 14 incisos): a query quoting an inciso has
    high lexical overlap with that single article but the article's semantic
    centroid is diluted across the other incisos. Cheap and deterministic — no
    BM25 dependency yet (deferred §38 full).
    """

    q_tokens = _tokenize(query)
    if len(q_tokens) < window:
        return 0.0
    chunk_tokens = _tokenize(chunk_text)
    if len(chunk_tokens) < window:
        return 0.0
    chunk_ngrams = {
        tuple(chunk_tokens[i : i + window])
        for i in range(len(chunk_tokens) - window + 1)
    }
    for i in range(len(q_tokens) - window + 1):
        if tuple(q_tokens[i : i + window]) in chunk_ngrams:
            return 1.0
    return 0.0


def composite_score(
    hit: VectorSearchResult,
    requested_article: str | None,
    *,
    query: str = "",
) -> tuple[float, float]:
    """Return ``(composite_score, semantic_score)`` for a hit (§38).

    The ``CITATION_WEIGHT`` slot carries the max of two signals so the §38
    weights stay unchanged: ``exact_citation_match`` (article-number citation)
    and ``phrase_overlap`` (verbatim n-gram quote). For queries with neither,
    behaviour is identical to before.
    """

    semantic = _clamp01(hit.score)
    authority = authority_for_payload(hit.payload)
    citation_num = exact_citation_match(hit.payload, requested_article)
    phrase = phrase_overlap(query, hit.text) if query else 0.0
    citation = max(citation_num, phrase)
    score = SEMANTIC_WEIGHT * semantic + AUTHORITY_WEIGHT * authority + CITATION_WEIGHT * citation
    return score, semantic
