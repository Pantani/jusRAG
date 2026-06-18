# JusRAG Brasil

**Copiloto open source de pesquisa jurídica brasileira com RAG: citações verificáveis, auditoria de claims e avaliação de fidelidade.**

Status: **v1.2** — API, ingestão do **CDC integral** (130 artigos do Planalto) + jurisprudência STJ ampliada (30 entradas — súmulas + repetitivos), vector search, hybrid retrieval **opt-in** (semantic + BM25), citações, auditor recalibrado, orquestração LangGraph, evals com quality gate sobre 158 perguntas + harness `eval-real` para providers reais, UI de demonstração. Fases 1–13 concluídas.

> ## Aviso de não aconselhamento jurídico
>
> Este projeto **não fornece aconselhamento jurídico**. Ele demonstra uma arquitetura de pesquisa jurídica assistida por IA, com RAG, fontes oficiais, citações verificáveis, versionamento jurídico e avaliação de fidelidade.
>
> Toda resposta tem finalidade **informativa** e é gerada com base nas fontes recuperadas pelo sistema. Ela **não substitui** a análise de um advogado ou profissional habilitado, especialmente porque a conclusão pode depender de fatos, documentos, datas e jurisprudência atualizada.

## O que é (e o que não é)

LLMs geram respostas jurídicas convincentes, mas podem **inventar** artigos, súmulas, decisões, teses e números de processo. Em direito, isso é crítico.

O JusRAG Brasil é um **copiloto de pesquisa** que ataca esse problema: nenhuma afirmação jurídica relevante é emitida sem uma fonte recuperada. Toda resposta percorre o encadeamento:

```
fonte → recuperação → ranking → síntese → auditoria → ressalva → avaliação
```

O sistema:

- recupera fontes jurídicas oficiais (seed) antes de responder;
- cita as fontes efetivamente usadas, com `chunk_id`, artigo/súmula e URL;
- separa legislação, jurisprudência, interpretação e ressalvas;
- audita afirmações sem suporte e **recusa com segurança** quando não há base suficiente;
- mede qualidade com evals offline (recall de retrieval, cobertura de citação, taxa de claims sem suporte, taxa de recusa segura).

**O diferencial é a arquitetura, não o LLM bruto.** Detalhes em [docs/legal-rag-design.md](docs/legal-rag-design.md) e [docs/architecture.md](docs/architecture.md).

Isto **não é**: um produto de aconselhamento jurídico, um peticionador automático, nem uma cobertura completa do direito brasileiro. Ver [docs/limitations.md](docs/limitations.md).

## Escopo do MVP

A v1.2 cobre **Direito do Consumidor**, com corpus seed expandido:

- **Legislação — CDC integral.** Código de Defesa do Consumidor (**Lei 8.078/1990**), texto compilado vigente, **130 chunks** (1 por artigo, do art. 1º ao 119, incluindo 42-A, 54-A..G, 104-A..C). Fonte: HTML oficial do Planalto (`planalto.gov.br/ccivil_03/leis/l8078compilado.htm`) **vendored** em `data/seed/cdc/_source/planalto_l8078compilado.html` (SHA256 fixado no frontmatter para auditoria). Loader determinístico HTML→markdown converte para o formato consumido pelo chunker.
- **Jurisprudência — STJ ampliada.** **30 entradas** consumer-específicas: **15 súmulas** (130, 297, 302, 321, 359, 385, 404, 472, 477, 479, 532, 543, 595, 608, 632) + **15 Temas repetitivos** (666, 717, 887, 932, 938, 939, 950, 952, 958, 960, 988, 990, 1006, 1020, 1030). Breakdown: **5 verified** (revisadas contra a fonte oficial) + **25 needs_review** (marcadas como pendentes de curadoria humana antes do release v1.2 final — campo `verification_status` no payload). Ver [docs/source-policy.md](docs/source-policy.md) e [docs/limitations.md](docs/limitations.md).

Perguntas fora desse recorte tendem a **recusa segura** — comportamento esperado, não falha.

## Arquitetura (resumo)

Em runtime, a pergunta passa por um grafo **LangGraph** ponta a ponta:

```
intake → classify_legal_area → retrieve_statutes / retrieve_case_law
       → rerank_and_select_context → synthesize_answer
       → audit_citations → check_risks → final_answer
```

A auditoria pode reescrever de forma conservadora ou levar à recusa; o `status` da resposta é um de `{running, needs_more_info, answered, refused, failed}`. Fluxo completo, camadas de código e schemas de domínio em [docs/architecture.md](docs/architecture.md).

## Stack

- **Backend:** Python 3.12+, FastAPI, Pydantic v2, pydantic-settings; pytest, ruff, mypy (strict).
- **IA / RAG:** embeddings OpenAI via interface abstrata (`EmbeddingProvider`), LLM via interface abstrata (`LLMProvider`), Qdrant para vector search, LangGraph para orquestração runtime. OpenSearch/BM25 e reranker têm interface preparada, opcionais na v1.
- **Infra local:** Docker Compose — `api`, `postgres`, `qdrant`, `redis`.
- **Observabilidade:** logs estruturados, `run_id` por execução, traces por etapa do grafo.

## Quickstart (do zero)

### 1. Clonar e validar offline (sem Docker, sem chave de API)

Esta trilha roda **100% offline** com fake providers determinísticos — não acessa rede.

```bash
git clone <repo> && cd jus-rag-brasil
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

make test            # pytest (sem rede externa)
make lint            # ruff check . && mypy packages apps
make ingest-cdc      # gera data/generated/cdc_chunks.jsonl (CDC arts 6/12/14/18/26/49)
make ingest-case-law # gera data/generated/case_law_chunks.jsonl (súmulas STJ 130/297/302/479/543)
make search-demo     # demo de busca semântica (fake embeddings)
make ask-demo        # demo de resposta citada via pipeline /ask (fake LLM)
make eval            # suíte de evals → data/generated/eval_report.{json,md} + quality gate
```

`search-demo`, `ask-demo` e `eval` usam fake providers e **não precisam** de Qdrant nem de `OPENAI_API_KEY`.

### 2. Stack real (Docker + Qdrant + OpenAI)

Pré-requisitos: Docker, Docker Compose e uma `OPENAI_API_KEY` válida no `.env`.

```bash
# .env: defina OPENAI_API_KEY=sk-...
make up              # docker compose up --build (api, postgres, qdrant, redis)

curl http://localhost:8000/health   # -> {"status": "ok"}

make ingest-cdc      # gera os chunks do CDC
make ingest-case-law # gera os chunks de jurisprudência (STJ)
make index-cdc       # indexa statute + case_law na collection Qdrant legal_chunks
```

`make index-cdc` requer Qdrant no ar **e** `OPENAI_API_KEY`. Sem a chave, o job **falha com erro explícito** — não há fallback silencioso para embeddings fake.

Endpoints:

```bash
# Busca, separando legislação e jurisprudência
curl -X POST http://localhost:8000/search \
  -H 'content-type: application/json' \
  -d '{"query": "direito de arrependimento na compra pela internet"}'

# Resposta citada, estruturada, com auditoria e aviso
curl -X POST http://localhost:8000/ask \
  -H 'content-type: application/json' \
  -d '{"question": "Posso desistir de uma compra feita pela internet?"}'
```

### 2b. Modo 100% local (sem OpenAI)

Trilha alternativa à 2: embeddings via `sentence-transformers` (in-process) e LLM via **Ollama** em container. Zero chamadas externas após o pull dos modelos.

**Pré-requisitos:** Docker, ~10 GB livres em disco, RAM ≥ 16 GB recomendada (modelos: `llama3.1:8b` ≈ 4.7 GB, `paraphrase-multilingual-mpnet-base-v2` ≈ 1 GB). Inferência em CPU é viável mas lenta — ver [docs/limitations.md](docs/limitations.md).

```bash
# a) .env: trocar providers
cp .env.example .env
# editar .env e ajustar/adicionar:
#   EMBEDDING_PROVIDER=local
#   LLM_PROVIDER=ollama
#   OLLAMA_BASE_URL=http://ollama:11434
#   LOCAL_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2
#   OLLAMA_CHAT_MODEL=llama3.1:8b
# (as 3 últimas ainda não estão no .env.example — adicione manualmente)

# b) Dependências do modo local (sentence-transformers + httpx)
pip install -e '.[local]'

# c) Subir stack com overlay que inclui o serviço `ollama` em :11434
docker compose -f docker-compose.yml -f docker-compose.override.local.yml up -d

# d) Baixar modelos para dentro do container (vai demorar — ~5 GB+ de download)
make pull-models

# e) IMPORTANTE: se a collection foi indexada antes com OpenAI (dim=1536),
#    é preciso recriar — embeddings locais têm dim=768 e o upsert quebra.
curl -X DELETE http://localhost:6333/collections/legal_chunks

# f) Reingestar e reindexar com os providers locais
make ingest-cdc && make ingest-case-law && make index-cdc

# g) Sondar
make ask-demo
# ou
curl -X POST http://localhost:8000/ask \
  -H 'content-type: application/json' \
  -d '{"question": "Posso desistir de uma compra feita pela internet?"}'
```

**Trade-off de qualidade.** `llama3.1:8b` é significativamente menos capaz que `gpt-4o-mini` / `gpt-4.1-mini` em síntese jurídica e formatação JSON estruturada. As regras invioláveis (§2/§40) seguem aplicadas — o auditor de citações é o gate, independente do provider —, mas espere mais recusas seguras e maior latência por inferência. Detalhes em [docs/limitations.md](docs/limitations.md).

**Alternativas:**
- **LLM:** `qwen2.5:7b-instruct` costuma ser mais robusto em saída JSON; troque `OLLAMA_CHAT_MODEL` e refaça `ollama pull` dentro do container.
- **Embeddings:** `nomic-embed-text` via Ollama (já pull-ed por `make pull-models`) como alternativa ao `sentence-transformers`. Mudança de modelo de embedding também exige recriar a collection.

### 3. UI de demonstração (Streamlit)

A UI consome o `/ask` existente — **apenas apresentação**, sem lógica de negócio jurídica. Streamlit é dependência **opcional** (grupo `demo`), fora do core para não pesar o install/test base.

```bash
pip install -e ".[demo]"
JUSRAG_API_URL=http://localhost:8000 streamlit run apps/web/app.py
```

A UI abre em `http://localhost:8501`. Para cada pergunta exibe: **resposta**, **fundamento legal** e **jurisprudência** em cards separados, **chunks usados**, **ressalvas**, **audit score** (com destaque quando a auditoria reprova) e o **aviso de não aconselhamento**. Requer a API no ar (passo 2) com a collection indexada. Roteiro completo em [docs/demo-script.md](docs/demo-script.md).

## Comandos `make`

| Comando | O que faz | Requer |
|---|---|---|
| `make test` | Roda a suíte de testes (pytest). | offline |
| `make lint` | `ruff check .` e `mypy packages apps`. | offline |
| `make format` | `ruff format .`. | offline |
| `make ingest-cdc` | Ingere o CDC seed → `data/generated/cdc_chunks.jsonl`. | offline |
| `make ingest-case-law` | Ingere súmulas STJ seed → `data/generated/case_law_chunks.jsonl`. | offline |
| `make search-demo` | Demonstração de busca semântica (fake embeddings). | offline |
| `make ask-demo` | Demonstração de resposta citada via `/ask` (fake LLM). | offline |
| `make eval` | Suíte de evals (fake providers determinísticos, CI). → relatório JSON + Markdown + quality gate. | offline |
| `make eval-real` | Mesma suíte com **providers reais** opt-in (OpenAI / sentence-transformers + Ollama). Uso: `EVAL_PROVIDER=openai OPENAI_API_KEY=sk-... make eval-real` ou `EVAL_PROVIDER=local make eval-real`. Pré-flight valida dim da collection Qdrant e disponibilidade de chave/Ollama antes de qualquer chamada paga. **Não roda em CI.** | Qdrant + chave/Ollama |
| `make up` | Sobe os serviços via Docker Compose. | Docker |
| `make down` | Derruba os serviços e remove volumes. | Docker |
| `make index-cdc` | Indexa os chunks na collection Qdrant `legal_chunks`. | Docker + `OPENAI_API_KEY` |

## Retrieval híbrido (opt-in)

Desde a v1.2, `HybridRetriever` aceita fusão **semantic + BM25** com pesos default `0.7 / 0.3` e normalização min-max por modalidade antes da fusão (ranking §38 preservado: `0.70 · hybrid + 0.20 · authority + 0.10 · exact_citation_match`). **Default: OFF** — `enable_hybrid=false` faz o retriever delegar 1:1 ao path semântico, preservando o baseline da Fase 3 bit-a-bit.

Habilitar:

```bash
# .env
ENABLE_HYBRID=true
HYBRID_SEMANTIC_WEIGHT=0.7
HYBRID_BM25_WEIGHT=0.3

# subir OpenSearch via profile dedicado
docker compose --profile hybrid up
```

Quando ativar: queries com **número de artigo explícito** ("art. 14 CDC...") ou **termos legais raros** que o embedding genérico confunde. `OpenSearchBM25Store` real ainda é stub (analyzer PT/stemmer pendentes — ver [docs/limitations.md](docs/limitations.md)); o `FakeBM25Store` cobre o caminho determinístico em testes.

## Qualidade e avaliação

`make eval` roda offline com fake providers determinísticos e impõe os quality gates da v1 (§36):

| Métrica | Threshold |
|---|---|
| `retrieval_recall_at_5` | ≥ 0.80 |
| `citation_coverage` | ≥ 0.90 |
| `unsupported_legal_claim_rate` | ≤ 0.05 |
| `refusal_when_no_source_rate` | ≥ 0.90 (perguntas fora do escopo) |

O gate da `unsupported_legal_claim_rate` é **sempre** enforçado (a regra "não alucinar", §2); os demais são enforçados por padrão e podem ser relaxados com `EVAL_GATE_STRICT=0` (apenas o gate de alucinação permanece). O job retorna código de saída não-zero quando um gate é violado, podendo **falhar o build**.

O golden dataset (`data/seed/questions/consumer_golden.yaml`) tem **158 perguntas** de Direito do Consumidor — **121 in-scope** (cobrindo todos os capítulos do CDC + súmulas e Temas STJ) + **37 out-of-scope** (tributário, penal, trabalho, família, sucessões, empresarial, administrativo, previdenciário, eleitoral, internacional, civil-reais) para validar recusa segura.

Métricas atuais sobre o golden ampliado (fake providers, `make eval`):

| Métrica | Valor | Threshold |
|---|---|---|
| `retrieval_recall_at_5` | **0.967** | ≥ 0.80 |
| `citation_coverage` | **1.000** | ≥ 0.90 |
| `unsupported_legal_claim_rate` | **0.000** | ≤ 0.05 |
| `refusal_when_no_source_rate` | **1.000** | ≥ 0.90 |

> **Honestidade sobre as métricas:** os valores acima são medidos com **fake providers determinísticos** offline para CI. Para medir com providers reais (OpenAI / sentence-transformers + Ollama) use `make eval-real` — manual, não-CI. Detalhes em [docs/evaluation.md](docs/evaluation.md).

## Limitações

Área única (consumidor), fonte seed restrita, jurisprudência inicial pequena, auditoria heurística e reranker opcional. Leia [docs/limitations.md](docs/limitations.md) antes de qualquer uso além de demonstração.

## Documentação

- [docs/architecture.md](docs/architecture.md) — arquitetura e fluxo runtime (LangGraph).
- [docs/legal-rag-design.md](docs/legal-rag-design.md) — desenho do Legal RAG, chunking e ranking.
- [docs/source-policy.md](docs/source-policy.md) — política de fontes oficiais e persistência.
- [docs/evaluation.md](docs/evaluation.md) — avaliação, métricas e quality gates.
- [docs/governance.md](docs/governance.md) — regras fundamentais, segurança e privacidade.
- [docs/limitations.md](docs/limitations.md) — limitações, não-objetivos e riscos.
- [docs/roadmap.md](docs/roadmap.md) — fases v0.0 → v1.0.
- [docs/demo-script.md](docs/demo-script.md) — roteiro de demo ponta a ponta.

## Licença

Ver [LICENSE](LICENSE).
