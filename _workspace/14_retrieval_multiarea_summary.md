# Fase D — Retrieval multi-área (indexação + autoridade + filtro por área)

Dono: retrieval (embeddings/storage/rag/jobs). Fecha a pendência da Fase B (ingestion):
`load_indexable_chunks()` agora inclui `statutes_chunks.jsonl`.

## 1. Como `load_indexable_chunks` mudou — `apps/worker/jobs/chunk_jsonl.py`

- Novo `STATUTES_CHUNKS_PATH = data/generated/statutes_chunks.jsonl` + helper
  `load_statutes_chunks(path)` (retorna `[]` se ausente — `make index-cdc` segue funcionando
  num checkout só-CDC; arquivo é gitignored/regenerável por `make ingest-codes`).
- `load_indexable_chunks()` passou a concatenar **CDC + statutes (7 códigos) + case_law** e a
  **deduplicar por `content_hash`** (primeiro vence). Salvaguarda contra overlap CDC↔statutes;
  hoje o overlap é **0** (medido: `statutes_chunks.jsonl` não contém o CDC — `norm_number=8078`
  tem 0 chunks lá; interseção de `chunk_id` = 0). A dedup é defensiva, não corretiva.
- Shape inalterado (um `LegalChunk` por linha); mesma collection `legal_chunks`; `legal_area`
  já é chave filtrável (`FILTERABLE_KEYS`). `index_cdc.py` só teve a docstring atualizada — a
  lógica de carga vem toda de `load_indexable_chunks`, então CDC e corpus completo compartilham
  exatamente o mesmo caminho.

## 2. Contagem total indexável (medido, fake provider, offline)

`load_indexable_chunks()` → **6329 chunks**:
- statute **6299** = 130 (CDC) + 6169 (CF/88 514, CC 2083, CP 423, CLT 1014, CTN 209, CPC 1080, CPP 846)
- case_law **30** (seed STJ; `case_law_chunks.jsonl`)

`run(FakeEmbeddingProvider, InMemoryVectorStore)` indexou os 6329 sem rede/Qdrant — confirma o
wiring embed→upsert do job para o corpus inteiro.

## 3. Decisão de job / Makefile (PENDÊNCIA p/ orquestrador — NÃO editei o Makefile)

- Novo job alias **`apps/worker/jobs/index_corpus.py`** = thin wrapper sobre `index_cdc.main`
  (mesma `load_indexable_chunks`, zero fork de lógica). Torna a intenção multi-área explícita no
  `make` sem duplicar pipeline.
- **Target proposto** (coordene comigo antes de aplicar):
  ```make
  index-corpus: $(COMPOSE_LOCAL) exec -T api python -m apps.worker.jobs.index_corpus
  ```
  `make index-cdc` permanece (compat / aceite Fase 3) e hoje **já indexa o corpus inteiro**, pois
  ambos chamam `load_indexable_chunks`. `index-corpus` é o nome semântico para o corpus statute
  completo (CDC + 7 códigos + case_law).

## 4. Regressão de autoridade decreto_lei / constituição — `tests/unit/rag/test_legal_ranker.py`

Confirmado em `legal_ranker.authority_for_payload` (lógica já correta, sem alteração de código):
- `norm_type=decreto_lei` (CP/CPP/CLT) → **0.95** (FEDERAL_LAW) — norm não-vazio ≠ constituição.
- `norm_type=constituicao` (CF/88) → **1.00** (CONSTITUTION).

Adicionados 2 testes de regressão: `test_decreto_lei_statute_resolves_federal_law`,
`test_constituicao_statute_resolves_constitution_tier`. Espelha `hierarchy.tier_for_statute`
(`_FEDERAL_LAW_NORMS` inclui `decreto_lei`).

## 5. Filtro por `legal_area` no retriever multi-área — `tests/unit/rag/test_retriever_multiarea.py`

Novo teste offline (`FakeEmbeddingProvider` + `InMemoryVectorStore`, padrão dos existentes, SEM
rede). Corpus mínimo civil (CC art. 186, `norm_type=lei`) + criminal (CP art. 121,
`norm_type=decreto_lei`) com texto lexicalmente sobreposto ("dano e ato ilícito") na mesma
collection:
- `legal_area="civil"` → só `civil-186` (penal excluído).
- `legal_area="criminal"` → só `criminal-121` (civil excluído).
- sem filtro → ambos. Isolamento vem do `payload_matches_filters` (igualdade sobre
  `legal_area`, top-level no payload §9), contrato §28 idêntico ao Qdrant.

## 6. Caminho de reindex real (NÃO roda neste ambiente — sem OPENAI_API_KEY/Docker garantido)

Job pronto; sequência exata para reindex real do corpus completo na collection `legal_chunks`:

```bash
# 0. infra + corpus
make up                       # Postgres, Qdrant, Redis
make ingest-cdc               # data/generated/cdc_chunks.jsonl (130)
make ingest-codes             # data/generated/statutes_chunks.jsonl (6169)  [target pendente Foundation]
python -m apps.worker.jobs.ingest_case_law   # case_law_chunks.jsonl (30)   [make ingest-case-law pendente]

# 1. DROP da collection (obrigatório: trocar de corpus/dim exige recriar — sem reuso silencioso)
curl -s -X DELETE "$QDRANT_URL/collections/legal_chunks"

# 2. reindex (a própria QdrantVectorStore recria a collection com a dim do provider)
make index-corpus             # == python -m apps.worker.jobs.index_corpus  [target pendente Foundation]
# enquanto o target não existe: python -m apps.worker.jobs.index_corpus
```

Notas de dimensão (system rule §6, sem fallback): vetor size é o do provider selecionado.
`EMBEDDING_PROVIDER=openai` (text-embedding-3-small, **dim 1536**) exige `OPENAI_API_KEY`;
`local` (`paraphrase-multilingual-mpnet-base-v2`, **dim 768**) é offline mas exige modelo baixado.
Trocar de provider sobre uma collection existente → o DELETE acima é obrigatório (dim divergente).

### Custo/escala esperado (~6329 chunks)
- **openai** text-embedding-3-small: ~6.3k requisições de embedding (em batch). Tamanho médio
  de artigo no corpus ~1.1 KB → grosso modo da ordem de 1.5–2.5M tokens de embedding no total.
  A $0.02 / 1M tokens (preço público text-embedding-3-small), custo de ordem de **US$ 0.03–0.05**
  por reindex completo. Tempo dominado por latência de rede + rate limit, não por CPU.
- **local** (sentence-transformers, dim 768): custo monetário zero; tempo ~minutos em CPU
  (ordem de 6.3k encodes). Recriar collection (dim 768 ≠ 1536) é obrigatório ao migrar de openai.
- Qdrant: 6.3k pontos × dim → ~10 MB (openai 1536) / ~5 MB (local 768) de vetores + payload §9;
  trivial para um nó Qdrant local. Upsert idempotente por `uuid5(chunk_id)`.

NÃO executei o reindex real (sem chave/garantia de Docker neste ambiente). Caminho offline
(fake + in-memory) validado acima.

## 7. Lint / testes (resultado real)

- `ruff check .` → **All checks passed!** (inclui C90 ≤ 10).
- `mypy packages apps` → **Success: no issues found in 97 source files**.
- `pytest tests/unit` (suíte unit completa) → **188 passed** (todos os arquivos).
- `pytest tests/unit/rag tests/unit/storage` → **34 passed** (inclui os 2 testes de autoridade
  novos + 3 de filtro multi-área).
- `run(FakeEmbeddingProvider, InMemoryVectorStore)` → **6329** chunks indexados offline.

## 8. Coordenação / contratos

- **Sem mudança de shape** do retriever (`RetrievedChunk`/`CitationRef`/`SeparatedRetrieval`
  inalterados) → CONTRACTS.md não precisa de novo shape; nenhum consumidor (answer/agentic)
  afetado. `legal_area` no filtro já constava do contrato §28 (`FILTERABLE_KEYS`).
- **Pendência aberta p/ FoundationAgent (Makefile):** target `index-corpus` (acima) e os já
  apontados pela ingestion (`ingest-codes`, `ingest-case-law`).

## Arquivos
- `apps/worker/jobs/chunk_jsonl.py` — `STATUTES_CHUNKS_PATH`, `load_statutes_chunks`, dedup em `load_indexable_chunks`.
- `apps/worker/jobs/index_corpus.py` (novo) — alias de indexação do corpus completo.
- `apps/worker/jobs/index_cdc.py` — docstring multi-área (lógica inalterada).
- `tests/unit/rag/test_legal_ranker.py` — +2 testes de autoridade (decreto_lei, constituicao).
- `tests/unit/rag/test_retriever_multiarea.py` (novo) — filtro por legal_area, offline.
