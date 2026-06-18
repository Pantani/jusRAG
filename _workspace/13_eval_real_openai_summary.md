# Fase 13.C.3 — Eval real com OpenAI (full 159q)

## Setup

- Provider: `EMBEDDING_PROVIDER=openai` + `LLM_PROVIDER=openai`
- Modelos: `text-embedding-3-small` (1536d) + `gpt-4.1-mini`
- Qdrant collection `legal_chunks` recriada do zero (volume novo), 160 pontos, dim 1536
  (130 CDC chunks + 30 case-law chunks).
- Golden: 159 entries (122 in-scope, 37 out-of-scope) em `data/seed/questions/consumer_golden.yaml`.
- Comando: `EMBEDDING_PROVIDER=openai EMBEDDINGS_MODEL=text-embedding-3-small LLM_PROVIDER=openai
  CHAT_MODEL=gpt-4.1-mini EVAL_PROVIDER=openai make eval-real`.

## Veredito

**Gate (strict §36): PASSED** em todas as 4 métricas obrigatórias.

## Tabela comparativa: fake (13.B.1) vs local (13.C.2) vs openai (13.C.3)

| Metric §36 | Threshold | Fake (159q) | Local (159q) | **OpenAI (159q)** | Δ openai vs fake |
|---|---|---|---|---|---|
| retrieval_recall_at_5 | ≥ 0.80 | 0.9669 | 0.8843 | **0.9754** | +0.009 |
| retrieval_precision_at_5 | — | 0.1934 | 0.1769 | 0.1951 | +0.002 |
| citation_coverage | ≥ 0.90 | 1.0000 | n/a (LLM timeout) | **1.0000** | 0 |
| unsupported_legal_claim_rate | ≤ 0.05 | 0.0000 | n/a | **0.0000** | 0 |
| refusal_when_no_source_rate | ≥ 0.90 | 1.0000 | n/a | **0.9189** | −0.081 |
| answer_relevancy (heuristic) | — | — | — | 0.9836 | — |
| faithfulness (heuristic) | — | — | — | 0.8689 | — |

Observação: o §2.2 (unsupported_legal_claim_rate) ficou em **0.0000** — abaixo do gate 0.05.
Sem FAIL crítico.

## Falhas (openai)

- **Retrieval (3 in-scope zero-recall)**: `cdc-pre-02`, `cdc-ab-04`, `cdc-ab-08`.
- **Answer / refusal (3 out-of-scope respondidos quando deveriam recusar)**: `oos-emp-01`,
  `oos-adm-02`, `oos-pre-02`.

## Regressões openai vs fake

### Retrieval

| Caso | fake | local | openai |
|---|---|---|---|
| `cdc-pre-02` | OK | FAIL | **FAIL (novo)** |
| `cdc-ab-04` | OK | OK | **FAIL (novo)** |
| `cdc-ab-08` | OK | OK | **FAIL (novo)** |
| `cdc-ab-07` | OK | FAIL | OK |
| `cdc-art-num-02` | OK | FAIL | OK |
| `cdc-cl-04`, `cdc-cl-08`, `cdc-de-07`, `cdc-de-10`, `cdc-inf-05`, `cdc-qu-03`, `cdc-qu-04`, `cdc-se-02`, `stj-19` | OK | FAIL | OK (recuperado pelo openai) |
| `cdc-art6-direitos-basicos`, `cdc-art6-educacao-consumo` | FAIL | OK | OK |

Padrão: openai recupera 11 das 12 regressões que o local introduziu sobre o fake; introduz 2 novas
falhas em queries adversariais de abuso (`cdc-ab-04`, `cdc-ab-08`) e mantém 1 já visto no local
(`cdc-pre-02`). Saldo líquido: +9 cases.

### Answer/refusal (out-of-scope respondidos indevidamente)

- `oos-emp-01`, `oos-adm-02`, `oos-pre-02` — gpt-4.1-mini respondeu em vez de recusar safely.
  Fake provider sempre recusava por construção; openai falha em 3/37 (8.1%) → métrica caiu de 1.0000
  para 0.9189 (ainda acima do gate 0.90, margem **0.019**).

**Risco**: margem de 1.9pp no único threshold §36 que regrediu. Endurecer o sentinel/refusal
heuristic no `AnswerWriter` (Fase v1.3) antes de subir o golden ou trocar para gpt-4o.

## Custo estimado

- Embeddings: 159 queries × ~50 tokens × $0.02/1M tokens ≈ **$0.0002**.
- Chat: 122 in-scope + 37 out-of-scope = 159 chamadas × ~3.0k input + 0.6k output tokens
  × ($0.4/1M in + $1.6/1M out) ≈ 159 × ($0.0012 + $0.00096) ≈ **$0.34**.
- **Total observado: ~$0.34** (orçamento $2 não atingido).

Indexação 160 chunks × ~250 tokens × $0.02/1M ≈ $0.001 (desprezível).

## Input para v1.3

1. **Refusal regressivo (oos-emp-01, oos-adm-02, oos-pre-02)** — gpt-4.1-mini está respondendo
   queries fora de Direito do Consumidor. Reforçar guardrail no prompt do `AnswerWriter`
   (whitelist de área) ou adicionar gate explícito antes do LLM.
2. **Retrieval adversarial (cdc-ab-04, cdc-ab-08)** — queries minimalistas sobre cláusulas
   abusivas dispersam o vetor. Considerar query expansion ou BM25 híbrido (já planejado §39 full).
3. Manter `cdc-pre-02` na lista de regressões persistentes desde 13.C.2 — gold-id pode estar
   incorreto; auditar manualmente.

## Artefatos

- Report JSON full: `_workspace/13_eval_real_openai_report.json`
- Report MD: `_workspace/13_eval_real_openai_report.md`
- Este summary: `_workspace/13_eval_real_openai_summary.md`
