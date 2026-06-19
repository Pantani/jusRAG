# Arquitetura

## Visão geral

O JusRAG Brasil é um pipeline de pesquisa jurídica em que **nenhuma afirmação jurídica relevante é emitida sem uma fonte recuperada**. O encadeamento conceitual é:

```text
fonte → recuperação → ranking → síntese → auditoria → ressalva → avaliação
```

## Fluxo runtime

```text
Usuário
  ↓
Web UI ou API
  ↓
FastAPI
  ↓
Legal Query Analyzer        # normaliza e interpreta a pergunta
  ↓
Legal Area Classifier       # identifica a área (MVP: consumer)
  ↓
Retriever Router
  ├── Statute Retriever      # legislação
  ├── Case Law Retriever     # jurisprudência
  ├── Precedent Retriever    # precedentes
  └── Metadata Retriever     # filtros por metadata
  ↓
Hybrid Retrieval
  ├── Qdrant vector search
  ├── OpenSearch BM25 (opcional)
  └── metadata filters
  ↓
Reranker                    # opcional na v1, interface preparada
  ↓
Legal Ranker                # scoring composto (ver docs/legal-rag-design.md)
  ↓
Context Builder             # monta o contexto citável
  ↓
Answer Writer               # síntese estruturada
  ↓
Citation Auditor            # verifica claims contra o contexto
  ↓
Risk Checker                # recusa segura / ressalvas
  ↓
Resposta final com fontes
```

## Camadas de código

O código vive sob dois roots (ver §5 da spec):

- **`apps/`** — entrypoints. `api/` (FastAPI: `main.py`, `dependencies.py`, `routes/`), `worker/jobs/` (CLIs dos alvos `make`), `web/` (demo Streamlit).
- **`packages/`** — bibliotecas reutilizáveis: `config/`, `legal_types/`, `ingestion/`, `embeddings/`, `llm/`, `storage/`, `rag/`, `agents/`, `answer/`, `evals/`, `observability/`.

Regra de fronteira: **não há lógica de negócio nas rotas FastAPI** — as rotas delegam para `packages/`. Embeddings, vector store, reranker e LLM provider são sempre acessados por **interfaces** (Protocols), mantendo as implementações concretas trocáveis.

## Dois orquestradores

A spec define dois orquestradores distintos que **não devem ser confundidos**:

1. **Orquestrador de implementação** — coordena os agentes de codificação paralelos por ownership de arquivo. É processo de engenharia, não roda em produção.
2. **Orquestrador runtime** — o grafo LangGraph que roda dentro do produto (introduzido na Fase 7). Mantém o estado `LegalResearchState` (pergunta, statutes/case-law recuperados, contexto selecionado, draft/final, resultado de auditoria, `status ∈ {running, needs_more_info, answered, refused, failed}`).

Na v1.0 o **LangGraph é o runtime** (`packages/agents/graph.py`, `run_graph`): `intake → classify_legal_area → retrieve_statutes / retrieve_case_law → rerank_and_select_context → synthesize_answer → audit_citations → check_risks → final_answer`. Falha de auditoria leva a uma reescrita conservadora e, persistindo, à recusa. (Versões anteriores à Fase 7 usavam um pipeline linear simples com os mesmos contratos.)

## Pipeline de ingestão

A ingestão é offline (jobs `apps/worker/jobs/`, alvos `make`) e transforma fonte oficial em chunks citáveis:

```text
loader → normalizer → chunker (por artigo) → versioning (content_hash) → JSONL
```

1. **Loader** (`packages/ingestion/loaders/`) — lê a fonte. No MVP, `LocalMarkdownLoader` lê o seed `data/seed/cdc/cdc.md`; loaders `planalto`, `lexml`, `stj`, `stf` ficam preparados para origens oficiais.
2. **Normalizer** (`packages/ingestion/normalizer.py`) — limpa e padroniza o texto antes de fatiar.
3. **Chunker** (`packages/ingestion/chunker.py`) — fatia **por estrutura normativa (artigo)**, preservando a unidade citável (`art. 12`, `art. 49`). Ver [legal-rag-design.md](legal-rag-design.md).
4. **Versioning** (`packages/ingestion/versioning.py`) — calcula `content_hash` (`sha256:...`) e `version`, garantindo reingestão idempotente no nível do hash. Ver [source-policy.md](source-policy.md).
5. **Saída** — `data/generated/cdc_chunks.jsonl`, uma linha por `LegalChunk`.

## Schemas de domínio (§8)

Definidos em `packages/legal_types/schemas.py` (Pydantic v2), com enums tipados em `enums.py`:

- **`LegalDocument`** — documento normativo: `document_id, doc_type, source, title, legal_area, country, jurisdiction, norm_type, norm_number, norm_year, version, source_url, content_hash, created_at, metadata`.
- **`LegalChunk`** — unidade citável: herda os campos do documento e acrescenta `chunk_id, article, paragraph, inciso, alinea, text`. O `chunk_id` é determinístico (`build_chunk_id` → `cdc-8078-1990-art-12`), o que sustenta a idempotência.
- **`LegalCitation`** — referência verificável: `citation_id, source, doc_type, title, source_url, article, case_number, court, judgment_date, publication_date, support_level, chunk_id`.
- **`CaseLawDocument`** — jurisprudência (usado a partir da Fase 6): `court, case_number, rapporteur, panel, judgment_date, publication_date, precedent_type, is_binding, ementa, full_text, ...`.

O payload de RAG (§9) deriva desses schemas; os enums (`StrEnum`) serializam como string, compatíveis com o payload Qdrant. A autoridade jurídica (§39) vem de `hierarchy.py`; vigência temporal de `temporal_validity.py`.

## Infra local

Docker Compose sobe `api`, `postgres`, `qdrant` e `redis`. Postgres guarda documentos, chunks e run logs; Qdrant guarda os vetores (collection `legal_chunks`); Redis é usado para cache/coordenação leve.
