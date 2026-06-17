# Fase 1 (v0.1) — UIDocsAgent — Resumo

Parte de documentação da Fase 1 concluída. Documentação da Fase 0 (docs/) entregue para suportar o bootstrap técnico.

## Arquivos criados

- `README.md` — visão, escopo MVP (CDC, Lei 8.078/1990, arts. 6º,12,14,18,26,49), stack (§3), como rodar do zero (cp .env.example .env; make up; make test; tabela de alvos §6), aviso de não aconselhamento (§41) em destaque.
- `docs/architecture.md` — arquitetura alvo e fluxo runtime (§4); dois orquestradores; camadas apps/ e packages/.
- `docs/source-policy.md` — fontes oficiais (Planalto/LexML/STJ/STF); persistência source+URL+versão+ingestion_date+content_hash; idempotência por hash; payloads §9.
- `docs/legal-rag-design.md` — desenho do Legal RAG; diferencial = arquitetura, não LLM; chunking por artigo; scoring composto (§38) e pesos de autoridade (§39); saídas estruturadas.
- `docs/limitations.md` — não é aconselhamento; fora de escopo v1 (§1); limitações de escopo/técnicas; tabela de riscos e mitigação.
- `docs/governance.md` — regras fundamentais (§2), regras de segurança (§40), privacidade de logs, ownership/contratos, DoD.
- `docs/evaluation.md` — quality gates (§36), métricas (§24), golden dataset, execução offline; placeholder coerente p/ Fase 8.
- `docs/roadmap.md` — fases v0.0 → v1.0 (§16–26) em tabela + critérios de aceite v1.
- `docs/demo-script.md` — placeholder do roteiro de demo; campos exigidos pela UI (§25); detalhado na Fase 9.

## Fora do meu ownership (não tocados)

Makefile, docker-compose.yml, .env.example, pyproject.toml, código apps/packages — pertencem ao FoundationAgent.

## Pendências / coordenação

- README documenta alvos make conforme §6, mas marca explicitamente que ingest/index/search/ask/eval entram nas fases 2+. Validar que `make up`/`make test`/`make lint`/`make format` rodam quando o FoundationAgent entregar o Makefile; corrigir com o agente dono se algum alvo falhar antes de marcar como pronto.
- Seção de demo do README e demo-script.md serão detalhados na Fase 9, coordenados com a UI.

## Fidelidade

Nenhuma fonte, número de lei ou métrica inventada; todo conteúdo rastreável à spec. PT-BR, docs enxutos.
