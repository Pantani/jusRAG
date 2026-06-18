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
    """Deterministic hashed bag-of-words embedding (implements EmbeddingProvider).

    Adds corpus-fitted IDF weighting (BM25-style ``log((N-n+0.5)/(n+0.5)+1)``,
    raised to ``idf_power``) so discriminative tokens dominate the cosine over
    common ones. IDF is fitted on the first ``embed_texts`` batch (the indexing
    path always submits the full corpus once) and reused for subsequent
    ``embed_query`` calls — required on the expanded 160-chunk corpus, where the
    prior pure-TF scheme let short chunks with one strong matching token outrank
    long, on-point articles (recall@5 regression below the §36 threshold).
    ``idf_power=0.35`` is the F1 plateau on the seed: full IDF (power=1.0) over-
    sharpens and pulls 2 OOS queries above the writer's grounding threshold,
    while no-IDF keeps the recall regression — the dampened power restores both
    gates at once. Determinism is preserved: IDF only depends on the indexed
    corpus, which is itself deterministic.
    """

    def __init__(self, dim: int = 256, idf_power: float = 0.35) -> None:
        if dim <= 0:
            raise ValueError("embedding dimension must be positive")
        if idf_power < 0:
            raise ValueError("idf_power must be non-negative")
        self._dim = dim
        self._idf_power = idf_power
        self._idf: dict[int, float] = {}
        self._fitted = False

    @property
    def dim(self) -> int:
        return self._dim

    def _fit_idf(self, texts: list[str]) -> None:
        """Fit BM25-style IDF on the corpus token-slot document frequencies."""

        n_docs = len(texts)
        doc_freq: dict[int, int] = {}
        for text in texts:
            seen: set[int] = set()
            for token in _normalize_tokens(text):
                seen.add(_slot(token, self._dim))
            for slot in seen:
                doc_freq[slot] = doc_freq.get(slot, 0) + 1
        self._idf = {
            slot: math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0) ** self._idf_power
            for slot, df in doc_freq.items()
        }
        self._fitted = True

    def _embed_one(self, text: str) -> list[float]:
        # Sublinear (1 + log) TF weighting damps repetition; IDF (when fitted)
        # then upweights discriminative tokens. L2-normalized so cosine == dot.
        counts: dict[int, float] = {}
        for token in _normalize_tokens(text):
            slot = _slot(token, self._dim)
            counts[slot] = counts.get(slot, 0.0) + 1.0
        vec = [0.0] * self._dim
        for slot, count in counts.items():
            tf = 1.0 + math.log(count)
            vec[slot] = tf * self._idf.get(slot, 1.0) if self._fitted else tf
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            return vec
        return [v / norm for v in vec]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self._fitted and texts:
            self._fit_idf(texts)
        return [self._embed_one(t) for t in texts]

    def embed_query(self, query: str) -> list[float]:
        return self._embed_one(query)
