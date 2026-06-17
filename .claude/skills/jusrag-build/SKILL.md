---
name: jusrag-build
description: >-
  Orquestrador de implementação do projeto jus-rag-brasil. Use SEMPRE que o pedido for
  implementar, construir, avançar, continuar, refazer, atualizar, corrigir ou validar
  qualquer parte do jus-rag-brasil — incluindo "implementar a spec", "rodar a Fase N",
  "fazer o bootstrap", "ingestão do CDC", "vector search", "/ask", "auditor de citações",
  "jurisprudência STJ", "LangGraph", "evals", "UI demo", "preparar o release v1.0", ou
  "continuar de onde parou". Coordena os agentes especialistas (foundation, legal-domain,
  ingestion, retrieval, answer, agentic, eval, ui-docs, qa) por fases. A fonte normativa é
  jus-rag-brasil-prompt-master.md na raiz. Não dispare para perguntas conceituais simples.
---

# jus-rag-brasil — Orquestrador de build

Conduz a implementação do `jus-rag-brasil` fase a fase, seguindo o **Prompt Master**
(`jus-rag-brasil-prompt-master.md`, raiz do projeto) como especificação única e normativa.
O orquestrador decide *quem* trabalha *quando*; os agentes em `.claude/agents/` executam; as
skills de conhecimento (`legal-rag-contracts`, `legal-rag-safety`, `legal-chunking`,
`legal-evals`) carregam o *como*.

## Por que este harness existe

A spec define 13 agentes e 10 fases em rodadas paralelas. Implementar tudo num único contexto
perde o isolamento de ownership (§54) e mistura responsabilidades. Separar em agentes com
ownership de arquivo disjunto + contratos validados entre fases reproduz a disciplina de
worktrees paralelos da spec dentro do Claude Code, com auditoria por artefato em disco.

## Modo de execução

**Híbrido com viés sub-agente.** Os agentes coordenam por **arquivos** (schemas tipados,
`cdc_chunks.jsonl`, contratos Protocol) e por **validação de contrato pelo orquestrador entre
fases** — não por chat ao vivo. Por isso usamos o Agent tool diretamente, não TeamCreate:

- Agentes independentes da mesma rodada: `Agent(..., model: "opus", run_in_background: true)`.
- Agentes com dependência: sequencial, esperando o artefato do anterior.
- **Todo `Agent` usa `model: "opus"`.** A qualidade do build depende do raciocínio do agente.
- QA roda **incrementalmente** após cada módulo entregue, não só no fim (ver `qa-agent`).

## Phase 0 — Contexto (sempre primeiro)

Antes de qualquer spawn, determine o modo de execução:

1. Leia `_workspace/STATE.md` se existir. Ele registra a última fase concluída e pendências.
2. Rode `make test` e `make lint` se já houver `Makefile`, para conhecer o baseline real.
3. Decida:
   - **Sem `_workspace/` e sem código** → execução inicial, comece pela Fase 1.
   - **`_workspace/` existe + pedido de "continuar"** → retome na próxima fase pendente do STATE.
   - **Pedido de parte específica** ("refazer o /ask", "Fase N") → re-execução parcial: só os
     agentes donos daquela fase, lendo os artefatos existentes e melhorando-os.
   - **Novo input que invalida artefatos** → mova `_workspace/` para `_workspace_prev/` e recomece.
4. Reporte ao usuário a fase-alvo e os agentes que serão acionados. Confirme antes de fases que
   reescrevem trabalho existente.

## Mapa de fases → rodadas → agentes

Segue §16–26 e §53 da spec. Cada fase só avança após cumprir seus **critérios de aceite**.

| Fase | Versão | Objetivo | Agentes (donos) | Aceite-chave |
|------|--------|----------|-----------------|--------------|
| 0 | v0.0 | Docs iniciais, arquitetura | ui-docs | docs/ explicam RAG, fontes, limitações |
| 1 | v0.1 | Bootstrap (FastAPI, Docker, settings, /health) | foundation, ui-docs | `make up`, `make test`, `GET /health`=ok |
| 2 | v0.2 | Schemas jurídicos + ingestão CDC | legal-domain, ingestion, ui-docs | `make ingest-cdc` gera JSONL; arts. 6,12,14,18,26,49; idempotente por hash |
| 3 | v0.3 | Embeddings + Qdrant + /search | retrieval | `make index-cdc`; `/search` retorna art.12 (defeito) e art.49 (arrependimento) |
| 4 | v0.4 | /ask com resposta citada | answer | `/ask` estruturado; sempre com `sources`; recusa segura; `not_legal_advice` |
| 5 | v0.5 | Auditor de citações | answer, eval | claims sem suporte detectados; `citation_coverage`/`unsupported_legal_claim_rate` |
| 6 | v0.6 | Jurisprudência STJ seed | ingestion, retrieval, answer | busca separa statute/case_law; resposta tem bloco jurisprudência |
| 7 | v0.7 | Orquestração LangGraph | agentic, answer | grafo ponta a ponta; estado final completo; falha de audit → revisão/recusa |
| 8 | v0.8 | Evals | eval, retrieval | `make eval`; ≥30 golden; recall@5, citation_coverage, unsupported rate |
| 9 | v0.9 | UI demo | ui-docs | UI local mostra resposta, fontes, caveats, audit, aviso |
| 10 | v1.0 | Release | foundation, ui-docs, qa | todos `make` alvo funcionam; CI; tag v1.0; README do zero |

QA (`qa-agent`) entra após cada fase de código (2–9) verificando o cruzamento de interfaces da
fase recém-concluída contra os contratos.

## Protocolo por fase

Para cada fase:

1. **Confirmar objetivo** e listar arquivos a criar/alterar (do ownership do agente — §12).
2. **Carregar contexto** do agente: o `.md` do agente já aponta as skills de conhecimento.
3. **Spawnar** os agentes da rodada (`model: "opus"`). Independentes em paralelo
   (`run_in_background: true`); dependentes em sequência.
4. **Coletar artefatos** em `_workspace/{fase}_{agente}_{artefato}` e no código real.
5. **Validar contratos** entre módulos (ver `legal-rag-contracts`). Divergência de shape → volta
   ao agente dono, não conserte no orquestrador.
6. **QA incremental** via `qa-agent` na interface da fase.
7. **Rodar** os `make` alvo da fase + `make test` + `make lint`. Reportar resultado real.
8. **Atualizar `_workspace/STATE.md`** (fase concluída, pendências, comandos validados).
9. **Resumo da fase** ao usuário com comandos verificados e próximos passos.

Nunca avançar de fase sem aceite cumprido. Se um critério falhar, registre como pendência e
decida com o usuário entre corrigir agora ou seguir com a lacuna documentada.

## Passagem de dados

- **Código real**: nos diretórios da spec (§5). É a entrega.
- **`_workspace/`**: artefatos intermediários e rastro de auditoria. Convenção de nome:
  `{fase}_{agente}_{artefato}.{ext}` (ex.: `02_legal-domain_schemas-summary.md`).
- **`_workspace/STATE.md`**: estado vivo do build (fase atual, aceites, pendências, baseline de
  testes). Lido na Phase 0 de toda re-execução.
- **`_workspace/CONTRACTS.md`**: snapshot dos contratos efetivos (Protocols + shapes de I/O) que o
  orquestrador usa para validar integração. Atualizado quando `legal-domain` muda schema.

## Erro e conflito

- Agente falha → 1 retry com o erro no prompt. Se refalhar, registre a lacuna no STATE e siga;
  não invente o artefato faltante.
- Dados/contratos em conflito entre agentes → não apague; registre ambos com origem e resolva via
  o agente dono do contrato (`legal-domain` para schemas).
- Mudança fora do ownership → proibida sem coordenação. Schemas compartilhados só por
  `legal-domain`; `Makefile`/`main.py` coordenados pelo orquestrador (§54).
- Teste com rede externa → proibido em unit; force fake providers (§13 da spec, contrato §27).

## Regras invioláveis (lembrete — detalhe em `legal-rag-safety`)

Nunca inventar fonte; toda afirmação jurídica relevante apoiada em fonte recuperada; recusa segura
sem fonte; separar legislação/jurisprudência/ressalva; aviso de não aconselhamento sempre; persistir
fonte+URL+versão+hash; sem lógica de negócio em rotas FastAPI; tudo via interface; sem secrets.

## Cenários de teste

**Fluxo normal — "implementar a Fase 1":** Phase 0 detecta sem código → confirma alvo Fase 1 →
spawna `foundation` (código) + `ui-docs` (README inicial) → coleta → `make up`/`make test`/
`GET /health` → QA confirma /health → STATE atualizado → resumo com comandos validados.

**Fluxo de erro — "continuar" com `make test` quebrado:** Phase 0 roda baseline, vê falha →
identifica fase/agente dono pelo STATE → re-spawna só esse agente com o output do teste →
revalida → se persistir após 1 retry, reporta a falha real e a lacuna ao usuário, sem marcar a
fase como concluída.

**Re-execução parcial — "refazer o auditor de citações":** Phase 0 = parcial → spawna `answer`
lendo `packages/answer/citation_auditor.py` atual + feedback → QA revalida contrato §31 → STATE.
