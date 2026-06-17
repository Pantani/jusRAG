# Fase 9 (v0.9) — UI demo — summary (ui-docs)

## Arquivos criados / alterados
- `apps/web/app.py` — app Streamlit (apresentação only, consome `POST /ask`).
- `apps/web/README.md` — como rodar e o que a UI exibe.
- `docs/demo-script.md` — roteiro de demo real (substitui placeholder da Fase 1).
- `README.md` — nova seção "Demo (UI Streamlit)" coordenada (install + comando streamlit).
- `pyproject.toml` — grupo opcional `[project.optional-dependencies] demo = [streamlit, httpx]`.

## O que a UI exibe (§25 / §12.12)
- campo de pergunta + slider `top_k` (sidebar);
- `short_answer` (resposta);
- **fundamento legal** (legislação) e **jurisprudência** em cards SEPARADOS (§2.3) —
  case_law: court, case_number, title, ementa, source_url;
- **fontes / chunks usados** em cards (doc_type, source, chunk_id, URL oficial);
- **caveats**;
- **audit**: citation_coverage, unsupported_legal_claim_rate (fallback `unsupported_rate`),
  passed — bloco `st.error` em destaque quando `passed=false` + lista de unsupported_claims;
- **aviso §41** sempre visível (st.warning no topo, antes de qualquer interação);
- `status=refused` → bloco de recusa segura claro;
- erro de conexão (ConnectError) / HTTP / HTTPError → mensagem clara, sem stack trace.
- Sem lógica de negócio jurídica: só renderiza o que a API devolve.

## Como rodar
```bash
make up && make ingest-cdc && make ingest-case-law && make index-cdc
pip install -e ".[demo]"
JUSRAG_API_URL=http://localhost:8000 streamlit run apps/web/app.py
```
`JUSRAG_API_URL` configurável (default http://localhost:8000).

## Deps adicionadas
- `[project.optional-dependencies].demo`: `streamlit>=1.39`, `httpx>=0.27`. NÃO no core
  (mantém install/test base leve). Outros grupos/core intactos.
- **Pendência:** ratificação do pyproject pelo FoundationAgent.

## Validado vs requer stack
Validado aqui (sem subir API+Qdrant):
- `pip install -e ".[demo]"` ok; `python -c "import apps.web.app"` ok.
- render contra o schema REAL `AnswerResponse` (model_dump) via stub do streamlit:
  payload answered, audit reprovado (confirma bloco de erro), e refused — todos renderizam.
- `ruff check .` → no issues; `mypy packages apps` → no issues (UI É type-checked pelo
  target lint; corrigido um `no-any-return` em `call_ask` com anotação explícita).
- `pytest tests` → 120+ unit e suíte completa passam, sem regressão. (Observação: a saída
  agregada do ambiente reporta "No tests collected" via um wrapper; o binário real
  `.venv/bin/python -m pytest tests` confirma todos passando.)

Requer stack (NÃO executado aqui, demo end-to-end NÃO foi rodada):
- `streamlit run` contra a API real + Qdrant indexado. O parsing/render foi provado contra
  o schema, mas o fluxo HTTP ponta a ponta depende de `make up` + index.

## Saída lint/test
- ruff: No issues found
- mypy packages apps: No issues found
- pytest tests: todos passam (120 unit; suíte completa verde, só StarletteDeprecationWarning).
```
