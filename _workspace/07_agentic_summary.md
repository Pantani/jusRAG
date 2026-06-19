# Fase 7 (v0.7) — Orquestração LangGraph (dono: agentic)

Pipeline RAG transformado em workflow agentic auditável com LangGraph real, sobre o
`LegalResearchState` (§13) exato. Reusa rag/answer/auditor — não reimplementa retrieval
nem síntese. Offline com fakes determinísticos.

## Status LangGraph: REAL (não fallback)

`langgraph==1.2.5` instalado no venv e adicionado a `pyproject.toml`
`[project.dependencies]` (`langgraph>=0.2`). **PENDÊNCIA de ratificação do foundation**:
mudança coordenada em `pyproject.toml` (dono nominal: FoundationAgent). Grafo compilado
via `StateGraph` + `START`/`END` + `add_conditional_edges` (API verificada por introspecção
da 1.2.5). Estado é Pydantic `BaseModel`; nós retornam dict parcial; `invoke` devolve dict
rehidratado em `LegalResearchState`.

## Arquivos

Criados em `packages/agents/`:
- `state.py` — `LegalResearchState` + `RetrievedSource` + `CitationAuditResult`, **exatamente**
  §13 (sem campos extras; `status` Literal de 5 valores).
- `graph.py` — `build_graph(...)`/`run_graph(...)`: `StateGraph` §14 + regras de roteamento + traces.
- `intake.py` — `run_intake` (§15.1): normaliza pergunta, extrai `facts`/`missing_facts`.
- `classify_area.py` — `run_classify_area`/`classify_area` (§15.2): consumer vs out-of-scope (controle de escopo robusto).
- `statute_researcher.py` — `make_statute_researcher` (§15.3): `SearchService` filtrado `doc_type=statute`.
- `case_law_researcher.py` — `make_case_law_researcher` (§15.4): filtrado `doc_type=case_law`.
- `precedent_analyzer.py` — `run_precedent_analysis` (§15.5): tagueia autoridade do precedente em metadata.
- `answer_writer.py` — `make_answer_writer` + `AnswerBuffer` (§15.6): reusa `build_context`/`build_answer`/`LLMProvider`.
- `citation_auditor.py` — estendido: `make_citation_auditor` + `to_state_audit` (§15.7), sobre o nó puro da Fase 5.
- `risk_checker.py` — `make_risk_checker` (§15.8): caveats + disclaimer §41 + `final_answer` + status terminal.
- `rerank_select.py` — `run_rerank_and_select_context` (§14): scope gate + união statutes/case_law.
- `_adapters.py` — `chunk_to_source`/`source_to_chunk` (RetrievedChunk ↔ RetrievedSource §13).
- `trace.py` — `TraceCollector`/`TraceStep` + `RETRY_MARKER`/`retry_attempts`/`visible_errors`.
- `__init__.py` — exporta `build_graph`/`run_graph`/state.

Testes: `tests/unit/agents/test_graph.py` (8 testes) + `__init__.py`.

## Diagrama do grafo (§14)

```text
START → intake ─┬─(missing_facts)→ needs_more_info ─────────────────────────┐
                └─→ classify_legal_area → retrieve_statutes → retrieve_case_law
                     → analyze_precedents → rerank_and_select_context
                         ├─(selected_context vazio)→ check_risks (refusal) ──┤
                         └─→ synthesize_answer → audit_citations             │
                                ├─(passed)──────────────→ check_risks ───────┤
                                ├─(falha, attempts<1)→ retry_synthesis ──┐    │
                                └─(falha, attempts≥1)→ check_risks ──────┼────┤
                                   retry_synthesis → synthesize_answer ──┘    │
                                                              check_risks → END
```

## Regras de roteamento §14 — como cada uma é implementada

1. **Fora de escopo e sem fonte → recusa.** `classify_area` marca a área (e injeta caveat
   se não-consumer); retrieval roda mesmo assim; `_route_after_select` envia direto a
   `check_risks` quando `selected_context` vazio → `risk_checker` finaliza `status=refused`
   sem inventar. (Prova: pergunta cripto → tax, sources=[], refused.)
2. **`missing_facts` crítico → needs_more_info.** `_route_after_intake`: se `missing_facts`
   não-vazio, vai a `needs_more_info` (marca status) → `check_risks` pede contexto.
3. **Audit falha → volta a synthesize 1×.** `_route_after_audit`: se `audit` não passou e
   `retry_attempts(errors) < 1`, vai a `retry_synthesis` (anexa `RETRY_MARKER` a `errors`,
   sem violar §13) → `synthesize_answer`. Na 2ª passada o nó descarta os claims que o audit
   anterior marcou (`_make_conservative`).
4. **Falha 2× → conservadora ou recusa.** Após 1 retry, `_route_after_audit` força
   `check_risks`. Se a 2ª síntese passou no audit → answered conservador; se ainda há claim
   sem suporte e nada resta → `build_answer` devolve refusal → `risk_checker` finaliza refused.

Limite de retry = 1 (`_MAX_SYNTHESIS_RETRIES`); contagem por `RETRY_MARKER` em `state.errors`
(filtrável por `visible_errors` para superfícies de usuário). Estado permanece **exato §13**.

## Traces por etapa (§3/§23)

`TraceCollector.record(run_id, step, status, note)` por nó (wrapper `_traced`), com log
estruturado `jusrag.agents` + lista em memória auditável (`for_run(run_id)`). Auditável sem
inflar o estado §13.

## Prova dos 3 cenários (saída real, fakes + InMemoryVectorStore)

```text
=== answered: 'O fornecedor responde por defeito do produto?'
status: answered | legal_area: consumer
trace: intake -> classify_legal_area -> retrieve_statutes -> retrieve_case_law ->
       analyze_precedents -> rerank_and_select_context -> synthesize_answer ->
       audit_citations -> check_risks
audit: (cov=1.0, unsup=0.0, passed=True) | sources: [art-18, art-12, art-49] | caveats: 3

=== refused: 'Qual a alíquota do imposto de renda sobre criptomoedas?'
status: refused | legal_area: tax
trace: intake -> classify_legal_area -> retrieve_statutes -> retrieve_case_law ->
       analyze_precedents -> rerank_and_select_context -> check_risks
audit: None | sources: [] | caveats: 3 | retry_markers: 0
final: "Não há base suficiente nas fontes recuperadas..."

=== audit-retry: 'O fornecedor responde por defeito do produto?' (LLM alucina art. 999)
status: answered | legal_area: consumer
trace: ... synthesize_answer -> audit_citations -> retry_synthesis -> synthesize_answer ->
       audit_citations -> check_risks
audit: (cov=1.0, unsup=0.0, passed=True) | retry_markers: 1
final: art. 999 removido; sobra art. 12 suportado.
```

Os 3 cenários também cobertos por `tests/unit/agents/test_graph.py` (answered/refused/retry +
needs_more_info + nós isolados intake/classify/answer_writer + contagem de retry).

## Deps adicionadas

`pyproject.toml [project.dependencies]`: `langgraph>=0.2` (instalado 1.2.5; puxa
langchain-core, langgraph-checkpoint/prebuilt/sdk, langsmith, orjson, tenacity…).

## Nota de tipagem (mypy strict)

LangGraph 1.2.5 tipa `add_node` com overloads sobre `StateNode[NodeInputT, ContextT]`; um valor
declarado `Callable[[State], dict]` não casa por limitação de binding de overload do mypy. Solução
limpa (sem `# type: ignore`): `_traced` retorna `StateNode[LegalResearchState, Any]` e a
`StateGraph` é parametrizada `StateGraph[LegalResearchState, Any, LegalResearchState, LegalResearchState]`.

## Validação

- `make lint` (ruff + mypy packages apps): **PASS** — `All checks passed!` / `Success: no issues found in 81 source files`.
- `make test` (pytest): **PASS** — `142 passed` (8 novos em agents; sem regressão).
- Script ponta-a-ponta dos 3 cenários: saída real acima.
- Complexidade ≤ 10 (ruff C90) e mypy strict mantidos.

## Pendências / integração

- **`/ask` sob `ENABLE_AGENT_GRAPH=true`**: NÃO integrado nesta entrega (ownership de
  `apps/api/routes/ask.py` é do answer; `settings.py`/DI do foundation). `run_graph` já oferece
  o ponto de entrada; integração coordenada na próxima rodada sem quebrar o caminho não-agentic.
- Ratificar `langgraph` no `pyproject.toml` (FoundationAgent).
- `IntakeAgent`/`LegalAreaClassifier` são heurísticos/offline (mesma assinatura de nó); trocar
  por LLM atrás do mesmo contrato é drop-in.
