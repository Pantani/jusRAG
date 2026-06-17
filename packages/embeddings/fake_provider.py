"""Deterministic, network-free embedding provider for tests and demos.

Approach
--------
This is a *lexical* embedding: a hashed bag-of-words over a normalized token
stream, projected onto a fixed-dimension vector and L2-normalized. Cosine
similarity between two such vectors therefore reflects weighted lexical overlap
between the texts — which is enough for the seed CDC corpus to satisfy the
acceptance queries ("defeito do produto" -> art. 12, "arrependimento" -> art. 49)
without any external model or network call.

Determinism comes from:
- Unicode-folding + lowercasing + stopword removal (stable normalization).
- A stable token hash (``blake2b``, not Python's salted ``hash``) to pick the
  vector slot for each token.
- A tiny domain synonym map so semantically-equivalent legal terms land on the
  same token (e.g. "desistencia"/"arrependimento" -> shared concept), giving the
  cosine a semantic, not purely surface, signal.

This is explicitly NOT a real embedding model: it captures lexical/concept
overlap only. The real provider (``OpenAIEmbeddingProvider``) replaces it in
production via the same Protocol.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Portuguese stopwords that carry no retrieval signal. Kept small and explicit.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "o",
        "os",
        "as",
        "um",
        "uma",
        "de",
        "do",
        "da",
        "dos",
        "das",
        "e",
        "ou",
        "que",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "por",
        "para",
        "com",
        "sem",
        "se",
        "ao",
        "aos",
        "the",
        "of",
        "art",
        "n",
        "ser",
        "sua",
        "seu",
        "suas",
        "seus",
        "pela",
        "pelo",
        "quando",
    }
)

# Domain synonym normalization: map surface terms to a shared concept token so
# the cosine reflects legal-concept overlap, not just identical word forms.
_SYNONYMS: dict[str, str] = {
    "arrependimento": "arrependimento",
    "arrepender": "arrependimento",
    "desistencia": "arrependimento",
    "desistir": "arrependimento",
    "reflexao": "arrependimento",
    "devolucao": "arrependimento",
    "defeito": "defeito",
    "defeituoso": "defeito",
    # Vício (art. 18/26) is a distinct CDC institute from defeito/fato do produto
    # (art. 12); keep them on separate concept tokens so retrieval can tell them
    # apart instead of collapsing both onto "defeito".
    "vicio": "vicio",
    "vicios": "vicio",
    "fabricante": "fabricante",
    "produtor": "fabricante",
    "produto": "produto",
    "produtos": "produto",
    "consumidor": "consumidor",
    "consumidores": "consumidor",
    "fornecedor": "fornecedor",
    "fornecedores": "fornecedor",
    "prazo": "prazo",
    "prazos": "prazo",
    "decadencial": "prazo",
    "reclamar": "reclamacao",
    "reclamacao": "reclamacao",
    "domicilio": "domicilio",
    "estabelecimento": "estabelecimento",
    # Jurisprudence (STJ súmulas) concept folding so consumer queries can recall
    # the seeded case law (e.g. "CDC aplica-se a banco" -> Súmula 297/479). Maps
    # surface forms (and their destemmed variants) onto a shared concept token.
    "cdc": "consumidor",
    "banco": "financeira",
    "bancario": "financeira",
    "bancaria": "financeira",
    "financeiro": "financeira",
    "financeira": "financeira",
    "instituicao": "instituicao",
    "instituico": "instituicao",  # destem("instituicoes") -> "instituico"
    "aplica": "aplicacao",
    "aplicavel": "aplicacao",
    "aplicaveis": "aplicacao",
    "aplicacao": "aplicacao",
}


def _destem(token: str) -> str:
    """Very light Portuguese plural folding: defeitos->defeito, vicios->vicio.

    Keeps it conservative (only trailing 's'/'es' on words >3 chars) to avoid
    mangling short tokens; enough to align singular/plural legal terms.
    """

    if len(token) > 4 and token.endswith("es"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def _normalize_tokens(text: str) -> list[str]:
    """Fold accents, lowercase, tokenize, drop stopwords, destem, apply synonyms."""

    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(folded.lower()):
        if raw in _STOPWORDS or len(raw) < 2:
            continue
        stem = _destem(raw)
        tokens.append(_SYNONYMS.get(stem, _SYNONYMS.get(raw, stem)))
    return tokens


def _slot(token: str, dim: int) -> int:
    """Stable, salt-free slot for a token (reproducible across processes)."""

    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % dim


class FakeEmbeddingProvider:
    """Deterministic hashed bag-of-words embedding (implements EmbeddingProvider)."""

    def __init__(self, dim: int = 256) -> None:
        if dim <= 0:
            raise ValueError("embedding dimension must be positive")
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def _embed_one(self, text: str) -> list[float]:
        # Raw term counts per slot, then sublinear (1 + log) TF weighting — the
        # classic IR damping so a term repeated N times doesn't dominate, which
        # otherwise lets verbose chunks outrank the on-point article.
        counts: dict[int, float] = {}
        for token in _normalize_tokens(text):
            slot = _slot(token, self._dim)
            counts[slot] = counts.get(slot, 0.0) + 1.0
        vec = [0.0] * self._dim
        for slot, count in counts.items():
            vec[slot] = 1.0 + math.log(count)
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            return vec
        return [v / norm for v in vec]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def embed_query(self, query: str) -> list[float]:
        return self._embed_one(query)
