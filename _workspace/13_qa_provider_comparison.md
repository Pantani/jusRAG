# Fase 13.B.3 — QA cross-provider sobre corpus expandido

Data: 2026-06-18
Modo: fake rodável; local e openai abortaram explicitamente em pré-flight (sem fallback silencioso, §6).

## Ambiente

- Qdrant local em `http://localhost:6333` (reachable).
- Ollama local em `http://localhost:11434` — modelos disponíveis: `llama3.1:8b`, `nomic-embed-text`, `llama3.2:1b`.
- `.env` aponta hostnames do compose (`qdrant`, `ollama`); overrides via `QDRANT_URL`/`OLLAMA_BASE_URL` para `localhost` foram necessários para rodar do host.
- Corpus indexado (fake, dim=256, recriado para os probes): **160 pontos** = 130 chunks CDC + 30 chunks STJ (Bloco A confirmado).
- `sentence-transformers` NÃO está instalado no venv; `pip install -e '.[local]'` foi negado pelo sandbox.
- `OPENAI_API_KEY` está vazio no `.env`.

## 1) Eval cross-provider

| Provider (emb/llm) | recall@5 | citation_coverage | unsupported_legal_claim_rate | refusal_when_no_source_rate | Gate §36 | Tempo wall |
|---|---|---|---|---|---|---|
| fake / fake | **0.9669** | **1.0000** | **0.0000** | **1.0000** | PASSED (strict) | ~6 s eval |
| local / ollama | N/A | N/A | N/A | N/A | N/A | — |
| openai / openai | N/A | N/A | N/A | N/A | N/A | — |

**Motivos do N/A (não-inventado):**

- `EVAL_PROVIDER=local`: aborta em `LocalEmbeddingProvider.embed_texts` com `RuntimeError: sentence-transformers not installed; install with 'pip install -e .[local]'`. Comportamento correto — sem fallback silencioso. Ollama está UP e modelos puxados, mas o eval nunca chega ao LLM porque o embedding falha antes (durante o reindex implícito do `build_real_harness`).
- `EVAL_PROVIDER=openai`: aborta em pré-flight: `OPENAI_API_KEY is not set; cannot run eval with provider 'openai'. Export it … or pick another provider.` Sem chave configurada.

**Tempos de reindex medidos** (mesmo dataset, 160 chunks):
- fake (256 dim): `ELAPSED_INDEX_FAKE=0s` (sub-segundo — função hash determinística).
- local (768 dim): N/A — falhou antes de iniciar (sentence-transformers ausente).
- openai (1536 dim): não tentado (sem chave).

## 2) Probes end-to-end (provider fake disponível)

API: `uvicorn apps.api.main:app --port 8000` com `EMBEDDING_PROVIDER=fake LLM_PROVIDER=fake`.

| # | Query | Provider | Status | Latência | n_sources | not_legal_advice | Qualidade qualitativa |
|---|---|---|---|---|---|---|---|
| P1 | celular com defeito após 60 dias | fake/fake | answered | 0.054 s | 3 (statute) | true | Recuperou art. 26 (prescrição vícios, esperado) e art. 18 indiretamente, MAS top-1 foi art. 99 (concurso de créditos) — ranking ruim sem similaridade real. Recall ok, precisão de topo fraca. |
| P1 | mesma | local/ollama | N/A | — | — | — | sentence-transformers ausente |
| P1 | mesma | openai/openai | N/A | — | — | — | OPENAI_API_KEY ausente |
| P2 | empréstimo bancário sem autorização | fake/fake | answered | 0.057 s | 8 (todas statute, 0 case_law) | true | Trouxe arts. 54-A/C/D/F/G (superendividamento) e 104-A/B (conciliação). NÃO trouxe art. 14 (responsabilidade do fornecedor) nem súmula 297 STJ — miss relevante. Sem case_law no resultado apesar do corpus ter 30 entradas STJ. |
| P2 | mesma | local/ollama | N/A | — | — | — | idem |
| P2 | mesma | openai/openai | N/A | — | — | — | idem |
| P3 | imposto sobre criptomoedas | fake/fake | **refused** | 0.050 s | 0 | true | Recusa segura correta (§2). Mensagem: "Não há base suficiente nas fontes recuperadas para responder a esta pergunta com segurança." |
| P3 | mesma | local/ollama | N/A | — | — | — | idem |
| P3 | mesma | openai/openai | N/A | — | — | — | idem |

Latência p50 (fake): ~54 ms — embedding fake é hash determinístico, sem rede.

## 3) Diffs fake vs real

Não há baseline real para comparar nesta janela. Hipóteses (não-numéricas, a confirmar quando providers reais estiverem disponíveis):

- **P1 e P2 devem melhorar substancialmente em openai/local**: o ranking de topo em fake é dominado pela hash do texto, não pela semântica — por isso art. 99 ("concurso de créditos") aparece acima de art. 26 em consulta sobre defeito. Embedding real deve corrigir.
- **P2 (fraude bancária)**: o fato de nenhuma case_law STJ aparecer com 30 entradas indexadas sugere que o router/ranker pode estar filtrando case_law por threshold de similaridade não atingido em fake. Verificar com embedding real antes de classificar como bug.
- **P3 (cripto/tributário)**: recusa deve permanecer em qualquer provider — está fora de escopo (MVP = consumidor) e o corpus não tem fontes tributárias. §2 OK.

## 4) §2 — Hallucination gate

- Nenhum provider rodável violou §2.
- P3 recusou corretamente em fake. Não foi possível testar P3 em providers reais; gate **não foi pode ser violado** em modos N/A porque o eval nem inicia.

## 5) Issues identificadas

| ID | Severidade | Owner sugerido | Descrição |
|---|---|---|---|
| 13.B.3-I1 | médio | retrieval | P2 (fraude bancária) deveria recuperar art. 14 + súmula 297 STJ; em fake mode trouxe só superendividamento. Pode ser limitação do embedding determinístico; **bloquear apenas se persistir em embedding real**. |
| 13.B.3-I2 | médio | retrieval/ranker | P1 (defeito celular) trouxe art. 26 mas com art. 99 acima — ranking sem composite-score útil em fake. Esperado melhorar em real. |
| 13.B.3-I3 | baixo | retrieval/router | Em P2, 8 fontes statute e 0 case_law mesmo com 30 entradas STJ indexadas. Investigar se o router está filtrando case_law indevidamente em fake mode. |
| 13.B.3-I4 | infra | foundation | Sandbox bloqueia `pip install -e '.[local]'`. Sem isso, `EVAL_PROVIDER=local` é não-executável em CI/QA — documentar pré-requisito no README ou pré-instalar no devcontainer. |
| 13.B.3-I5 | infra | foundation | `.env` usa hostnames do docker-compose (`qdrant`, `ollama`); rodar do host exige overrides manuais. Considerar fallback automático para `localhost` quando DNS falha, ou separar `.env.local`. |

## 6) Comandos executados (auditoria)

```bash
# Baseline fake
EVAL_PROVIDER=fake make eval-real
# → Gate (strict): PASSED

# Tentativa local (falhou em pré-flight de extras)
QDRANT_URL=http://localhost:6333 OLLAMA_BASE_URL=http://localhost:11434 \
  EMBEDDING_PROVIDER=local LLM_PROVIDER=ollama EVAL_PROVIDER=local make eval-real
# → RuntimeError: sentence-transformers not installed

# Tentativa openai (falhou em pré-flight de chave)
QDRANT_URL=http://localhost:6333 EVAL_PROVIDER=openai EMBEDDING_PROVIDER=openai \
  LLM_PROVIDER=openai OPENAI_API_KEY= make eval-real
# → OPENAI_API_KEY is not set; cannot run eval with provider 'openai'.

# Reindex fake para probes
curl -X DELETE http://localhost:6333/collections/legal_chunks
QDRANT_URL=http://localhost:6333 EMBEDDING_PROVIDER=fake LLM_PROVIDER=fake make index-cdc
# → Indexed 160 chunk(s) into Qdrant collection 'legal_chunks'.

# API e 3 probes
uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 &
curl -X POST http://127.0.0.1:8000/ask -d '{"question":"..."}'
```

## 7) Veredito

- Bloco baseline (fake): **PASS** — todos os gates §36 verdes, §2 respeitado, probe de recusa correta.
- Cross-provider real: **INCONCLUSIVO** — ambiente não habilita `local` (extras ausentes) nem `openai` (chave ausente). Aborta de forma explícita em ambos os casos, como exigido por §6 (sem fallback silencioso).
- Recomendação: re-executar 13.B.3 com `pip install -e '.[local]'` permitido e `OPENAI_API_KEY` exportado antes de declarar Fase 13 fechada.
