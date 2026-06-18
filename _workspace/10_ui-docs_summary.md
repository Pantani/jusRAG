# Fase 10 — UIDocsAgent (DOCS) — summary

## Escopo

Parte DOCS da Fase 10 (v1.0 release). Ownership: `README.md` e `docs/`. Não tocou em código, pyproject, Makefile, .github.

## Arquivos alterados

- `README.md` — reescrito do zero (v1.0).
- `docs/evaluation.md` — reescrito para refletir `run_all` real.
- `docs/roadmap.md` — fases 1–9 marcadas done, v1.0.
- `docs/limitations.md` — súmulas STJ seed explicitadas (130/297/302/479/543).
- `docs/architecture.md` — runtime LangGraph como o motor da v1.0 (removido fraseado prospectivo "até a Fase 7").

## Inalterados (já consistentes com v1.0)

- `docs/source-policy.md`, `docs/legal-rag-design.md`, `docs/governance.md`, `docs/demo-script.md` (Fase 9). Conferidos; sem inconsistências.

## Estrutura do novo README

1. Título + frase-síntese (§1) + status v1.0 (fases 1–9 done).
2. Aviso de não aconselhamento (§41), proeminente (blockquote H2).
3. O que é / o que não é — encadeamento `fonte→...→avaliação`.
4. Escopo MVP: CDC arts 6/12/14/18/26/49 + súmulas STJ 130/297/302/479/543.
5. Arquitetura resumida (grafo LangGraph runtime) + link architecture.md.
6. Stack.
7. Quickstart do zero: (1) trilha OFFLINE com fakes [clone → cp .env → venv → pip install -e ".[dev]" → test/lint/ingest/search-demo/ask-demo/eval]; (2) trilha STACK REAL [make up + OPENAI_API_KEY → ingest → index-cdc → curl /search, /ask]; (3) UI Streamlit demo.
8. Tabela de make targets com coluna "Requer" (offline / Docker / Docker+OPENAI_API_KEY).
9. Qualidade e avaliação: tabela dos 4 gates §36 + semântica do gate (alucinação sempre; EVAL_GATE_STRICT=0) + nota de honestidade (seed pequeno + fake provider).
10. Limitações (link), Documentação (8 links), Licença.

## Validação dos comandos (README ↔ realidade)

- Todos os 11 alvos do README existem no `Makefile`. ✓
- Classificação offline vs stack confere: `index-cdc` é o único que precisa Qdrant+OPENAI_API_KEY (embeddings reais, sem fallback silencioso); `search-demo`/`ask-demo`/`eval` rodam com fakes offline. ✓
- Grupos `dev` e `demo` existem em `pyproject.toml`; `apps/web/app.py` existe; env `JUSRAG_API_URL`. ✓
- Golden: 31 perguntas (≥30). `EVAL_GATE_STRICT`, gate de alucinação sempre-on, relatório em `data/generated/eval_report.{json,md}` — conferem com `run_all.py`. ✓
- Nós do grafo no README/architecture batem com `packages/agents/graph.py` (`run_graph`, intake→classify→retrieve→rerank/select→synthesize→audit→risk→final). ✓

## Não executado

Não rodei `make` (sem alterar código). Validação foi por leitura cruzada de Makefile, pyproject, run_all.py, graph.py, app.py, golden yaml.
