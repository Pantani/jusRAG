# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

This is a **greenfield repository**. The only content is [jus-rag-brasil-prompt-master.md](jus-rag-brasil-prompt-master.md) — the single source of truth specifying the entire `jus-rag-brasil` project. No code, `pyproject.toml`, `Makefile`, `docker-compose.yml`, or directory structure exists yet. Build the project by executing the phases defined in the prompt master, in order.

When implementing, **the prompt master overrides any assumption**: directory layout (§5), env vars (§7), domain schemas (§8), inter-module contracts (§27–31), and per-phase acceptance criteria (§16–26) are normative. Read the relevant section before creating files in a module.

## What this project is

JusRAG Brasil — an open-source Brazilian legal-research copilot built on RAG with **verifiable citations, claim auditing, and faithfulness evaluation**. It is *not* a legal-advice product; every answer must carry a non-advice disclaimer. MVP scope is **Direito do Consumidor** (CDC, Lei 8.078/1990), seeded with arts. 6º, 12, 14, 18, 26, 49.

The differentiator is the architecture, not raw LLM output. Every legal answer must pass through:
`fonte → recuperação → ranking → síntese → auditoria → ressalva → avaliação`.

## Stack

Python 3.12+, FastAPI, Pydantic v2 + pydantic-settings, pytest, ruff, mypy. RAG: OpenAI embeddings (behind an abstract interface), Qdrant vector store, LangGraph orchestration (from the agentic phase), OpenSearch BM25 optional. Local infra via Docker Compose: Postgres, Qdrant, Redis. LangGraph is introduced only at Phase 7 — earlier phases use a plain pipeline.

## Target commands

These come from the spec's Makefile (§6). They do not exist yet — create them in Phase 1 (FoundationAgent owns the `Makefile`).

```bash
cp .env.example .env
make up            # docker compose up --build
make down          # docker compose down -v
make test          # pytest
make lint          # ruff check . && mypy packages apps
make format        # ruff format .
make ingest-cdc    # python -m apps.worker.jobs.ingest_cdc   → data/generated/cdc_chunks.jsonl
make index-cdc     # python -m apps.worker.jobs.index_cdc    → Qdrant collection legal_chunks
make search-demo   # python -m apps.worker.jobs.search_demo
make ask-demo      # python -m apps.worker.jobs.ask_demo
make eval          # python -m packages.evals.run_all        → eval report JSON + Markdown
```

Run a single test with `pytest path/to/test_file.py::test_name`. Tests must **not** hit external network by default — use the fake providers.

## Architecture

Runtime request flow (§4): FastAPI → Query Analyzer → Area Classifier → Retriever Router (statute / case-law / precedent / metadata) → Hybrid Retrieval (Qdrant vector + optional OpenSearch BM25 + metadata filters) → Reranker → Legal Ranker → Context Builder → Answer Writer → Citation Auditor → Risk Checker → final answer with sources.

Code lives under two roots (§5):
- `apps/` — `api/` (FastAPI: `main.py`, `dependencies.py`, `routes/`), `worker/jobs/` (CLI entrypoints for the `make` targets), `web/` (Streamlit demo).
- `packages/` — the libraries: `config/`, `legal_types/`, `ingestion/` (loaders, normalizer, chunker, versioning), `embeddings/`, `llm/`, `storage/` (postgres, qdrant, opensearch, repositories), `rag/`, `agents/` (LangGraph nodes + state + graph), `answer/`, `evals/`, `observability/`.

Two distinct orchestrators (§10): the **implementation orchestrator** (coordinates parallel coding agents by file ownership) and the **runtime orchestrator** (the LangGraph that runs inside the product). Don't conflate them.

### Key interface contracts (§27–31)

These are `Protocol`s — keep concrete implementations swappable and free of framework coupling.
- `EmbeddingProvider` — `embed_texts(list[str]) -> list[list[float]]`, `embed_query(str) -> list[float]`. Fake provider must be deterministic.
- `VectorStore` — `upsert_chunks(chunks, vectors)`, `search(query_vector, top_k, filters)`. Must not know about FastAPI or the LLM; returns objects carrying score + metadata.
- `AnswerWriter` output is the structured shape `{short_answer, legal_basis[], case_law[], caveats[], sources[], not_legal_advice: true}`.
- `CitationAuditor` output: `{citation_coverage, unsupported_legal_claim_rate, unsupported_claims[], passed}`.

The runtime graph state is `LegalResearchState` (§13) — a Pydantic model threading `question`, retrieved statutes/case-law, selected context, draft/final answer, audit result, and `status ∈ {running, needs_more_info, answered, refused, failed}`.

## Non-negotiable system rules (§2, §40)

These bind **every** module:
1. Never invent an article, law, súmula, decision, thesis, or case number.
2. Every relevant legal claim must be backed by a retrieved source; if support is insufficient, **refuse safely** rather than answer.
3. Keep legislation, jurisprudence, interpretation, and caveats clearly separated; always include the non-advice disclaimer (§41).
4. Persist source, URL, version, ingestion date, and `content_hash` for every document/chunk; re-ingestion must be idempotent at the hash level.
5. **No business logic inside FastAPI routes** — routes delegate to `packages/`.
6. Always go through interfaces for embeddings, vector store, reranker, and LLM provider.
7. No secrets, API keys, or large dumps committed. No real personal data or sigiloso processes in seed data.
8. Unit tests never depend on external network — use fake providers; seed data stays small and reproducible.

## Legal ranking (§38–39)

MVP composite score (before BM25 exists): `0.70·semantic_similarity + 0.20·legal_authority + 0.10·exact_citation_match`. Full version adds BM25, binding weight, recency, and source quality. Authority weights: Constituição 1.00, lei federal vigente / súmula vinculante / STF repercussão geral 0.95, STJ repetitivo 0.90, STJ súmula 0.88, STJ acórdão 0.75, TJ 0.60, doutrina 0.40, blog 0.20, unknown 0.10.

## Quality gates (§36)

v1 thresholds the eval suite enforces: `retrieval_recall_at_5 ≥ 0.80`, `citation_coverage ≥ 0.90`, `unsupported_legal_claim_rate ≤ 0.05`, `refusal_when_no_source_rate ≥ 0.90` for out-of-scope questions. `make eval` may fail the build when the unsupported-claim rate exceeds threshold. Golden dataset lives at `data/seed/questions/consumer_golden.yaml` (≥30 questions for v1).

## Harness: jus-rag-brasil build

**Objetivo:** implementar a spec `jus-rag-brasil-prompt-master.md` fase a fase, com agentes
especialistas de ownership disjunto coordenados por contratos validados em disco.

**Trigger:** para qualquer pedido de implementar/avançar/refazer/validar parte do `jus-rag-brasil`
(bootstrap, ingestão CDC, vector search, /ask, auditor, jurisprudência, LangGraph, evals, UI, release,
"continuar"), use a skill `jusrag-build`. Perguntas conceituais simples podem ser respondidas direto.

**Componentes:** orquestrador em `.claude/skills/jusrag-build/`; conhecimento reutilizável em
`legal-rag-contracts`, `legal-rag-safety`, `legal-chunking`, `legal-evals`; 9 agentes em
`.claude/agents/` (foundation, legal-domain, ingestion, retrieval, answer, agentic, eval, ui-docs, qa).
Modo de execução: híbrido com viés sub-agente (Agent tool, `model: opus`), coordenação por arquivo +
validação de contrato entre fases. Estado do build em `_workspace/STATE.md`.

**Restrições de execução:** evals/QA não usam rede (fake providers determinísticos); QA roda
incrementalmente após cada fase comparando interfaces produtor↔consumidor contra os contratos.

**Histórico de mudanças:**

| Data | Mudança | Alvo | Motivo |
|------|---------|------|--------|
| 2026-06-16 | Configuração inicial do harness | agents/* + skills/* + orquestrador | Build da spec jus-rag-brasil |

## Conventions

- **Conventional Commits** (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`).
- Branch naming and git-worktree-per-agent strategy in §11; parallel-agent file ownership in §12 and §54 — respect ownership, and coordinate shared files (`main.py`, `Makefile`, `README.md`, shared schemas) rather than editing them ad hoc.
- Definition of Done (§55): code + relevant tests written and passing, lint/typing not worse, docs updated when needed, no secrets, no external calls in unit tests, the phase's `make` commands work, acceptance criteria met.
