# Tarefa 13.A.3 — Hybrid Retrieval (semantic + BM25), default OFF

## Decisão de normalização: min-max (por modalidade, dentro do pool de candidatos)

Escolhido min-max sobre os scores brutos de cada modalidade, independentemente,
antes da fusão ponderada.

Por quê não softmax:

- BM25 raw é não-limitado e depende fortemente da estatística do corpus (df/idf
  + tf por termo). Cossenos vivem em [-1, 1] (normalmente [0, 1]). Softmax sobre
  scores tão heterogêneos colapsa a cauda longa de hits lexicais marginais perto
  de zero e, simultaneamente, achata os topos em quase-empate — perdendo a
  resolução que o BM25 oferece justamente para boost de matches exatos (e.g.
  "art. 14").
- Min-max preserva o espaçamento relativo dentro de cada modalidade e produz uma
  mistura [0, 1] estável que se encaixa direto nos pesos §38 (0.70/0.20/0.10).
- Degenerescência (todos iguais ou pool unitário): tratada explicitamente
  (`hi - lo < 1e-12` → flat 1.0) para a modalidade contribuir simetricamente em
  vez de zerar.

Pesos default (validados em `Settings`): `hybrid_semantic_weight=0.7`,
`hybrid_bm25_weight=0.3`, soma == 1.0 (tolerância 1e-6) — `ValidationError`
explícito caso contrário.

## FakeOpenSearchAdapter offline

`packages/storage/opensearch.py::FakeBM25Store`:

- Implementa o Protocol `BM25Store` (mesma forma de saída que
  `VectorSearchResult`, com `chunk_id/score/text/payload/metadata`).
- Tokeniza com `re.compile(r"\w+", re.UNICODE)`, lowercased.
- Mantém `payloads`, `tokens` por chunk e contagem `df` por termo.
- Score = `sum(tf[term] * idf(term))` sobre termos únicos da query —
  TF-IDF simples, não-BM25 puro (sem k1/b/length-norm), mas estável,
  determinístico e sem rede. Suficiente para (a) recompensar matches exatos que
  o dense embedding pode confundir e (b) provar o caminho de fusão.
- `idf(t) = log((1+N)/(1+df)) + 1` (suavização para evitar zero e log negativo).
- Reindexação idempotente: ao reindexar um `chunk_id` existente, decrementa `df`
  dos tokens antigos antes de reinjetar os novos.
- Sort estável: `(-score, chunk_id)` — duas execuções com mesma entrada produzem
  mesmo ranking (validado em `test_hybrid_fake_opensearch_deterministic`).

`OpenSearchBM25Store` é stub (NotImplementedError) com TODO para foundation —
nenhum sinal lexical falso vaza para o ranking quando o container OpenSearch
estiver desligado.

## Integração no ranking §38

Quando `enable_hybrid=True`, o `HybridRetriever`:

1. Faz embed da query → busca dense (over-fetch `top_k*3` ou ≥16).
2. BM25.search(query) com mesmos filtros e `top_k`.
3. Dedup por `chunk_id`; normalização min-max independente por modalidade.
4. `hybrid_score = w_sem * sem_norm + w_bm25 * bm25_norm`.
5. Score final §38 substitui `semantic_similarity` por `hybrid_score`:
   `0.70 * hybrid + 0.20 * authority + 0.10 * exact_citation_match`.
   Pesos 0.70/0.20/0.10 preservados, conforme item 3 da tarefa.

Quando `enable_hybrid=False` (default), `HybridRetriever.retrieve` delega 1:1
para `LegalRetriever` — zero mudança de comportamento, baseline Fase 3
preservado bit-for-bit.

## Testes novos (`tests/unit/rag/test_hybrid_retriever.py`)

- `test_hybrid_disabled_matches_semantic_baseline`: para 3 queries distintas,
  scores arredondados são idênticos ao retriever puro. **PASS**
- `test_phase3_acceptance_still_green_with_hybrid_off`: defeito→12,
  arrependimento→49 com hybrid OFF. **PASS**
- `test_hybrid_enabled_boosts_exact_article_match`: adiciona art. 14 ao seed;
  query "art. 14 CDC defeito serviço" com hybrid ON ranqueia art. 14 ≤ posição
  de semantic-only (BM25 sobre "serviço" não regrede o ordering, idealmente
  amplia). **PASS**
- `test_hybrid_weights_validation`: pesos 0.5+0.3 e 0.8+0.3 → `ValidationError`;
  0.6+0.4 ok. **PASS**
- `test_hybrid_fake_opensearch_deterministic`: 2 runs = mesmo ranking. **PASS**

## Suite completa

`python -m pytest`: **177 passed, 3 failed** (failures pré-existentes em
`tests/evals/test_*` — `refusal_when_no_source_rate=0.57 < 0.9`, baseline
verificado por `git stash + pytest`, não relacionado a esta tarefa).

`ruff check .` → All checks passed.
`mypy packages apps` → Success: no issues found in 92 source files.

Complexidade ciclomática: nenhuma função nova excede 10
(`HybridRetriever._rank` ~5, `_merge_candidates` ~4, `FakeBM25Store.search` ~5).

## docker-compose

Serviço `opensearch` adicionado sob `profiles: [hybrid]` — opt-in via
`docker compose --profile hybrid up`. Não roda no fluxo default; nenhum impacto
em `make up` atual. Image: `opensearchproject/opensearch:2.13.0`, single-node,
security desabilitada (local dev).

### TODO(foundation)

- Habilitar plugin `analysis-icu`/`analysis-nori` ou tokenizer/stemmer
  português antes do uso real (atualmente apenas `standard` analyzer).
- Hardening: habilitar security/TLS, tuning de heap, healthcheck, volume
  backups para uso fora de dev local.
- Implementar `OpenSearchBM25Store` real (índice `legal_chunks`, query
  `multi_match` com `text^2 + title`) — atualmente NotImplementedError.

## Arquivos tocados

- `packages/config/settings.py` (+ validator + 3 fields)
- `packages/rag/hybrid_retriever.py` (rewrite)
- `packages/storage/opensearch.py` (Protocol + FakeBM25Store + stub)
- `docker-compose.yml` (opensearch service, profile hybrid)
- `tests/unit/rag/test_hybrid_retriever.py` (novo)

`legal_ranker.py` NÃO foi alterado — a substituição "semantic → hybrid_score"
acontece no `HybridRetriever._rank` reusando as constantes públicas
(`SEMANTIC_WEIGHT`, `AUTHORITY_WEIGHT`, `CITATION_WEIGHT`), evitando duplicação
e mantendo o ranker single-source-of-truth dos pesos §38.
