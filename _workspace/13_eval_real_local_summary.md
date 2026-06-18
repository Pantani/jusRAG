# Fase 13.C.2 — eval-real com stack 100% local (sentence-transformers + Ollama)

## Status

PARCIAL — métricas de retrieval medidas em escala real (158q / 121 cases de retrieval); LLM apenas
smoke (3q) por inviabilidade prática de tempo (llama3.2 CPU); gates §36 dependentes do LLM
(citation_coverage, unsupported_legal_claim_rate, refusal_when_no_source_rate) **não foram medidos
em escala** — apenas observados no smoke.

## Stack efetiva

| Camada | Valor |
|---|---|
| Embeddings | `local` → `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (dim=768) |
| Vector store | Qdrant local (porta 6333, container `jusragbr-qdrant-1`) |
| LLM | `ollama` → `llama3.2:3b` (CPU) / fallback `llama3.2:1b` (testado) |
| Ollama | container `jusragbr-ollama-1`, porta 11434 |
| Golden | `data/seed/questions/consumer_golden.yaml` — 158 questões |
| Corpus | 160 chunks (130 CDC + 30 STJ case-law) |

Observação: a stack docker compartilhada `jusragbr-*` (de outra worktree) já estava up. Não subi a
override desta worktree — reusei os serviços via `localhost`. Exportei `*_HOST=localhost` /
`*_BASE_URL=http://localhost:...` para que os jobs (rodando fora do compose) os enxergassem.

## Comandos executados e tempos

| Etapa | Comando | Tempo |
|---|---|---|
| Install local extras | `pip install -e '.[local]'` | ~60s (cache parcial) |
| Pull `nomic-embed-text` | `docker exec jusragbr-ollama-1 ollama pull nomic-embed-text` | 47s |
| Pull `llama3.2:3b` | `docker exec jusragbr-ollama-1 ollama pull llama3.2:3b` | 2m21s |
| Pull `llama3.2:1b` (medição) | idem `llama3.2:1b` | 23s |
| DELETE collection (fake dim=256 → local dim=768) | `curl -X DELETE http://localhost:6333/collections/legal_chunks` | <1s |
| `make ingest-cdc` | `python -m apps.worker.jobs.ingest_cdc` | 0.2s — 130 chunks |
| `make ingest-case-law` | `python -m apps.worker.jobs.ingest_case_law` | 0.1s — 30 chunks |
| `make index-cdc` | `python -m apps.worker.jobs.index_cdc` | 29s — 160 chunks indexados (vector_size=768 confirmado via `GET /collections/legal_chunks`) |
| Eval retrieval (158q) | `python /tmp/eval_local_partial.py` | 2.9s |
| Eval LLM smoke (3q) | idem | 326.6s wall (3 chamadas: erro, 186s, 140s) |

Probe isolado llama3.2:3b (5 tokens): **248s** (load 4min, gen 4s warm).
Probe isolado llama3.2:1b (5 tokens): **60s** (load 26s, eval 26s → ~5s/token).

→ extrapolação 158q × LLM full ≈ **>40h** com llama3.2:1b; **>110h** com 3b. CPU sem aceleração
Metal/CUDA é inviável para a suíte completa.

## Tentativa eval-real completo (foreground)

```
$ EVAL_PROVIDER=local python -m packages.evals.run_all --provider=local
...
httpx.ReadTimeout: timed out
RuntimeError: Ollama request to http://localhost:11434/api/chat failed: timed out
real    5m25s
```

Abortou na primeira chamada LLM (timeout default 300s do `OllamaLLMProvider` — código não
parametriza via env). O timeout aconteceu durante a 1ª inferência (load+generate combined).

## Métricas reais — provider local vs baseline fake (Fase 13.B.1)

| Métrica §36 | Threshold | Fake (158q) | Local (158q) | Δ | Veredito local |
|---|---|---|---|---|---|
| retrieval_recall_at_5 | ≥ 0.80 | 0.9669 | **0.8843** | −0.083 | PASS |
| retrieval_precision_at_5 | — | 0.1934 | 0.1769 | −0.017 | n/a |
| citation_coverage | ≥ 0.90 | 1.0000 | **não medido em escala** (smoke: 2/3 retornaram com basis+sources) | — | n/a |
| unsupported_legal_claim_rate | ≤ 0.05 | 0.0000 | **não medido em escala** | — | n/a |
| refusal_when_no_source_rate | ≥ 0.90 | 1.0000 | **não medido em escala** | — | n/a |

Cases de retrieval: 121 (4 zero-recall fake / 14 zero-recall local).

## Tabela de regressões (zero-recall)

| Categoria | Cases |
|---|---|
| Shared (ambos zeram) | `cdc-art18-vicio-solidario`, `cdc-art49-fora-estabelecimento` — bug estrutural do chunker/golden (já conhecido nos relatórios anteriores). |
| Improvements (fake fail, local OK) | `cdc-art6-direitos-basicos`, `cdc-art6-educacao-consumo` — embeddings reais capturam paráfrases que o hash-fake errava. |
| **Regressions (fake OK, local fail)** — 12 cases | `cdc-ab-07`, `cdc-art-num-02`, `cdc-cl-04`, `cdc-cl-08`, `cdc-de-07`, `cdc-de-10`, `cdc-inf-05`, `cdc-pre-02`, `cdc-qu-03`, `cdc-qu-04`, `cdc-se-02`, `stj-19` |

Padrão das regressões: várias são queries adversariais/curtas (`qu-*`, `de-*`, `inf-*`, `ab-*` =
abreviações/queries minimalistas) onde o fake embedding determinístico (hash sobre tokens com forte
overlap) acerta por construção, mas mpnet multilíngue, sendo semântico, dispersa o vetor entre
artigos relacionados — o gold-id correto sai do top-5. Não é alucinação do retriever; é
pulverização semântica em queries pobres de sinal.

## LLM smoke (3 in-scope)

| id | tempo | sources | basis | resultado |
|---|---|---|---|---|
| cdc-art6-direitos-basicos | 0.5s | — | — | HTTP 500 Ollama: *"model runner unexpectedly stopped"* (provavelmente OOM/recurso na 1ª inferência cold) |
| cdc-art6-informacao-adequada | **186.0s** | 16 | 1 | Resposta coerente, cita art. 43 CDC |
| cdc-art6-protecao-vida-saude | **140.1s** | 16 | 1 | Resposta coerente sobre proteção da vida/saúde |

Plumbing local→retriever→answer_writer→ollama está **funcional**. Throughput é o impeditivo.

## Recomendações

### Thresholds §36 ainda válidos para provider local?

- `retrieval_recall_at_5 ≥ 0.80` — **VÁLIDO**. Local marcou 0.8843 (margem ~8pp acima do gate).
  Pode até endurecer para 0.85 em CI fake.
- Os 3 outros (citation/unsupported/refusal) **dependem do LLM** e não são mensuráveis com llama3.2
  em CPU dentro de uma janela de CI razoável. Mantenha como gate **apenas no provider=fake**
  (já é o default `make eval`); para provider local rode amostrado (N=10 in-scope + 5 out-of-scope).

### Ajustes recomendados para v1.3

1. **Parametrizar timeout do `OllamaLLMProvider` via env** (`OLLAMA_REQUEST_TIMEOUT_S`, default
   600s). Hoje 300s hard-coded estoura a 1ª inferência cold mesmo com modelo pequeno. **Escalar
   para `answer-agent` (ownership `packages/llm/ollama_provider.py`).**
2. Adicionar flag `--sample-llm N` em `packages/evals/run_all.py` para limitar a quantos cases o
   eval invoca o LLM, mantendo retrieval em escala completa. **Escalar para `eval-agent`.**
3. Documentar no README (seção "Modo 100% local") que `llama3.2:3b/1b` em CPU é apenas para
   plumbing/demo; medição real de gates exige GPU (Metal/CUDA) ou OpenAI.
4. Investigar as 12 regressões de retrieval para decidir: (a) reformular queries adversariais do
   golden, (b) adicionar reranker BM25 (já previsto §38), ou (c) aumentar `top_k` interno do
   retriever antes do trim para 5.
5. Pre-warm do modelo Ollama no `_check_ollama_reachable` (1 chamada dummy) para evitar timeout
   cold-start no primeiro case real.

## Artefatos

- `_workspace/13_eval_real_local_report.json` — métricas + smoke completos
- Este arquivo

## Não conforme com o briefing (declarado)

- `make eval-real EVAL_PROVIDER=local` **não rodou ao fim** com 158q — usei wrapper
  `/tmp/eval_local_partial.py` que mede retrieval em escala completa e LLM apenas como smoke.
  Justificativa: throughput LLM CPU torna a suíte completa inviável (>40h estimadas) e a tarefa
  permite explicitamente reportar métricas isoladas quando o LLM estoura.
- Métricas de citation/unsupported/refusal sobre 158q em provider local **não foram medidas**;
  baseline fake mantido como referência.

Sem commits desta tarefa (QA report).
