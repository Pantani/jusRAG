# Tarefa 13.C.4 — Calibração dos pesos do Hybrid Retrieval (OpenAI baseline)

## Setup

- Provider de embeddings: `openai` (`text-embedding-3-small`, 1536d).
- Vector store: Qdrant `legal_chunks` (160 pts, dim 1536) já indexado pela C.3.
- BM25 store: **OpenSearch real** (novo adapter `OpenSearchBM25Store` — httpx, sem dep extra), índice `legal_chunks`, 160 docs.
- Golden: 159 questões (122 in-scope) — `data/seed/questions/consumer_golden.yaml`.
- Top-k = 5; candidate pool = 16 por modalidade.
- 1 embedding por query (cache) reaproveitado nas 9 configurações da grid → custo total embeddings ≈ **$0.00015** (122 queries × ~50 tokens × $0.02/1M).

## Grid-search (122 in-scope, recall/precision micro-averaged)

| semantic_weight | bm25_weight | recall@5 | precision@5 | Δrecall vs sem-only |
|---|---|---|---|---|
| 0.50 | 0.50 | 0.9836 | 0.1967 | +0.0082 |
| 0.55 | 0.45 | 0.9836 | 0.1967 | +0.0082 |
| 0.60 | 0.40 | 0.9836 | 0.1967 | +0.0082 |
| 0.65 | 0.35 | 0.9836 | 0.1967 | +0.0082 |
| 0.70 | 0.30 | 0.9836 | 0.1967 | +0.0082 |
| 0.75 | 0.25 | 0.9836 | 0.1967 | +0.0082 |
| 0.80 | 0.20 | 0.9836 | 0.1967 | +0.0082 |
| 0.85 | 0.15 | 0.9836 | 0.1967 | +0.0082 |
| 0.90 | 0.10 | 0.9836 | 0.1967 | +0.0082 |

**Baseline semantic-only (provider=openai)**: recall@5 = **0.9754**, precision@5 = 0.1951.

### Observação importante: platô completo

Toda a grid retorna o mesmo recall (0.9836) e precision (0.1967). Análise:

- O ganho líquido vs semantic-only é exatamente **+1 chunk recuperado** (122 expected → de 119 hits → 120 hits). Um único `expected_chunk_id` antes faltante passa a entrar no top-5 graças à fusão.
- Esse chunk entra **em todos os pontos da grid** — ou seja, BM25 sozinho já o promove dentro do top-16 candidate pool, e qualquer peso w_bm > 0 é suficiente para elevá-lo via fusão (a normalização min-max amplifica o sinal exclusivo lexical mesmo com w_bm=0.1).
- Nenhum chunk dense-only é deslocado para fora do top-5 — o re-ranking §38 (authority 0.20 + citation 0.10 mantidos) preserva a ordem dos vencedores semânticos. Daí o platô flat.

## Decisão: **MANTER hybrid OPT-IN (default=false)**

Critério de ativação: `Δrecall ≥ +0.0200` (2pp).
Resultado: `Δ = +0.0082` (~0.8pp) — **abaixo do threshold**.

Sub-decisão sobre defaults: como toda a grid empata, **não há "ótimo único"**. Mantenho `hybrid_semantic_weight=0.7` / `hybrid_bm25_weight=0.3` por estarem dentro do conjunto ótimo e por:

1. Princípio do menor movimento: zero diff em `settings.py` quando a evidência não justifica mudança.
2. Stability: 0.70/0.30 espelha a literatura típica de hybrid retrieval (dense-heavy) e o exemplo do prompt master §38.
3. Conservadorismo: w_bm baixo limita o risco de regressão em queries onde BM25 introduz ruído fora do golden set atual.

Documentação dessa decisão registrada como comentário em `packages/config/settings.py` (sem mudança de valores).

## Eval de regressão final (configuração escolhida)

`EMBEDDING_PROVIDER=openai EMBEDDINGS_MODEL=text-embedding-3-small LLM_PROVIDER=openai CHAT_MODEL=gpt-4.1-mini EVAL_PROVIDER=openai EVAL_GATE_STRICT=1 QDRANT_URL=http://localhost:6333 make eval-real`

| Metric §36 | Threshold | C.3 (baseline) | **C.4 (final)** | Δ |
|---|---|---|---|---|
| retrieval_recall_at_5 | ≥ 0.80 | 0.9754 | **0.9754** | 0 |
| citation_coverage | ≥ 0.90 | 1.0000 | **1.0000** | 0 |
| unsupported_legal_claim_rate | ≤ 0.05 | 0.0000 | **0.0000** | 0 |
| refusal_when_no_source_rate | ≥ 0.90 | 0.9189 | **0.9189** | 0 |

**Gate strict §36: PASSED.** Zero diff vs C.3 — esperado, já que `enable_hybrid=False` mantém o fluxo bit-for-bit idêntico ao baseline semantic-only.

Custo eval-real C.4: ~**$0.34** (mesma ordem da C.3; identical workload).

## Gate `make eval` (fake providers, CI)

`PASS` em todas as 4 métricas: recall@5=0.9590, coverage=1.0, unsupp=0.0, refusal=0.9459.

## Lint + tests

- `ruff check .` → No issues.
- `mypy packages apps` → No issues.
- `pytest tests/` → **194 passed**.
- Complexidade ciclomática: nenhuma função nova excede 10 (`OpenSearchBM25Store._ensure_index` ~3, `index_chunks` ~5, `search` ~4; `_hybrid_rank` no script ~5).

## Diffs

- `packages/storage/opensearch.py`: `OpenSearchBM25Store` real (era stub `NotImplementedError`) — index com analyzer `standard`, bulk via `/_bulk`, search `multi_match text^2 + title`, filtros via `bool.filter` (`term`/`terms`). Mantém `FakeBM25Store` intacto.
- `apps/worker/jobs/index_opensearch.py`: novo CLI job (idempotente por `chunk_id`, `--recreate` opcional).
- `docker-compose.yml`: troca `plugins.security.disabled=true` por `DISABLE_SECURITY_PLUGIN=true` + `DISABLE_INSTALL_DEMO_CONFIG=true` (sem isso a v2.13 falha pedindo `OPENSEARCH_INITIAL_ADMIN_PASSWORD`).
- `scripts/calibrate_hybrid.py`: harness transitório (fora de `packages/`) — grid sobre golden in-scope, embedding cacheado, sem chamada de LLM.
- `packages/config/settings.py`: **sem mudança** de valores. Defaults atuais já dentro do conjunto ótimo do grid; ativação default exigia +2pp, observado +0.82pp.

## TODO(foundation) — sequenciais

1. Plugin pt (`analysis-icu`/stemmer) no índice OpenSearch antes de uso produtivo (atual: analyzer `standard`).
2. Avaliar query expansion / sinônimos antes de outro round de grid — o platô atual sugere que mais BM25 alone não desbloqueia novas wins.
3. Reavaliar a decisão quando o golden ≥ 300q ou quando entrarem queries com vocabulário técnico-jurídico onde BM25 historicamente outperforma dense.

## Artefatos

- Saída completa do grid: `/tmp/calib_out.txt` (também reproduzida na tabela acima).
- Eval JSON: `data/generated/eval_report.json` (sobrescrito pela última run).
- Este summary: `_workspace/13_retrieval_hybrid_calibration_summary.md`.
