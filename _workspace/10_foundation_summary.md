# Fase 10 — Foundation (INFRA/CI) — resumo

Data: 2026-06-17. Ownership: pyproject.toml, Makefile, docker-compose, CI.

## 1. CI — `.github/workflows/ci.yml`

- Triggers: `push` (todas as branches) + `pull_request`. `concurrency` cancela runs antigos por ref.
- Job `lint-test`: checkout → setup-python 3.12 (cache pip) → `pip install -e ".[dev]"` → `make lint` → `make test`.
- Job `eval` (separado, `needs: lint-test`): mesma instalação → `make eval` (gate §36, offline).
- **Offline por design**: sem Docker, Qdrant, Redis, Postgres ou `OPENAI_API_KEY`. Tudo roda nos fake providers determinísticos (regras §6/§8). Rápido (test ~1s; install dominante).
- Actions pinadas: `checkout@v4`, `setup-python@v5`.
- YAML validado: `python -c "yaml.safe_load(...)"` → OK.

## 2. Decisão de deps (pyproject.toml) — ratificada

Padrão de import verificado em disco:
- `openai` → import **lazy** (dentro do construtor / `TYPE_CHECKING`) em embeddings/llm openai_provider.
- `qdrant-client` → import **lazy** (dentro de métodos) em storage/qdrant.py.
- `langgraph` → import **TOP-LEVEL** em `packages/agents/graph.py`, **exercido por** `tests/unit/agents/test_graph.py`.

**Trade-off avaliado**: mover o stack RAG para um grupo `[rag]` opcional (já que testes usam fakes).
- Contra-argumento decisivo 1: `langgraph` é top-level e está no import path dos testes → fora do core, `make test`/`make lint` **quebram**. Sozinho isso obriga langgraph a ficar no core.
- Contra-argumento 2: `make lint` roda `mypy packages apps` sobre **todos** os módulos. Mesmo lazy, openai/qdrant precisam resolver tipos no type-check; sem o grupo instalado o CI quebraria no lint.
- Benefício de um grupo opcional (core leve) não se concretiza porque o gate de CI (lint+test) já requer os três.

**Decisão**: manter `qdrant-client>=1.12`, `openai>=1.54`, `langgraph>=0.2` no `[project.dependencies]` (core), com comentários explicando o porquê. Streamlit permanece isolado em `[project.optional-dependencies].demo` (a UI nunca é importada pelo core). Desduplicado/comentado `httpx` (dev = TestClient; demo = cliente do /ask). Lower bounds mantidos (sensatos, batem com o que foi instalado/testado nas fases). Dívida do STATE (deps adicionadas por retrieval/agentic/ui fora de ownership) → **ratificada**.

`pip install -e ".[dev]"` continua suficiente para lint+test+eval verdes.

## 3. Matriz make targets — offline vs stack

| Target | Modo | Observação |
|--------|------|-----------|
| test | offline | fake providers, 164 passed |
| lint | offline | ruff + mypy strict (88 files) |
| format | offline | ruff format |
| ingest-cdc | offline | gera data/generated/cdc_chunks.jsonl |
| ingest-case-law | offline | gera case_law_chunks.jsonl |
| search-demo | offline | InMemory/fake provider |
| ask-demo | offline | fake LLM + fake embeddings |
| eval | offline | gate §36 com fakes |
| up | **requer Docker** | sobe api+postgres+qdrant+redis |
| down | requer Docker | |
| index-cdc | **requer stack** | Qdrant no ar + `OPENAI_API_KEY` |

`index-cdc` sem `OPENAI_API_KEY`: comportamento **correto, sem fallback silencioso** — `OpenAIEmbeddingProvider()`
levanta `RuntimeError: OPENAI_API_KEY is not set; ...` (validado). Não mascarado.

## 4. Saídas reais validadas

- `python -c yaml.safe_load(ci.yml)` → `ci.yml YAML OK`
- `make lint` → `ruff All checks passed!` + `mypy Success: no issues found in 88 source files`
- `make test` → `164 passed, 1 warning in 1.03s` (warning: StarletteDeprecationWarning no TestClient, benigno)
- `make eval` → todas as 4 métricas PASS; `Gate (strict): PASSED`; exit 0

## 5. Pendência para o retrieval (não invadida — ownership de apps/worker/jobs/index_cdc.py)

- Opcional (§3 da tarefa): permitir `index-cdc` rodar offline com `EMBEDDING_PROVIDER=fake` (FakeEmbeddingProvider)
  para demo sem OpenAI. Exigiria seleção de provider em `apps/worker/jobs/index_cdc.py:main()` (hoje instancia
  `OpenAIEmbeddingProvider()` direto). **Não feito** (fora do ownership de foundation; não-trivial). Reportado
  para retrieval avaliar. Sem isso, `index-cdc` permanece stack-only com erro explícito — aceitável.

## 6. Notas

- README/docs **não tocados** (ui-docs reescreve em paralelo). packages/* não tocados.
- `make up` simultâneo dos 4 serviços continua pendente de ambiente Docker estável (dívida do STATE, ambiental).
