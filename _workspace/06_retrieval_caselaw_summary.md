# Fase 6 (v0.6) — Retrieval: separação statute / case_law (lado RetrievalAgent)

Fonte: §4, §9, §22 (aceite), §38–39 (ranking/autoridade). Consome o JSONL de
jurisprudência entregue pela ingestão (`data/generated/case_law_chunks.jsonl`,
`LegalChunk` com `doc_type=case_law` e payload §9 em `metadata`).

## Mudanças (ownership retrieval)

- **`packages/rag/legal_ranker.py`** — `authority_for_payload` agora resolve a
  autoridade de `case_law` a partir de `payload["metadata"]` (precedent_type/court):
  `_case_law_authority` → **STJ súmula = 0.88** (`AuthorityTier.STJ_SUMMARY`), não mais
  o fallback genérico 0.75. STF → 0.95, STJ acórdão → 0.75, TJ → 0.60. Statute inalterado.
- **`apps/worker/jobs/chunk_jsonl.py`** — `CASE_LAW_CHUNKS_PATH`,
  `load_case_law_chunks()` (vazio se o arquivo não existe → jurisprudência só aparece
  com fonte, §22) e `load_indexable_chunks()` = statutes + case_law.
- **`apps/worker/jobs/index_cdc.py`** — indexa AMBOS (cdc + case_law) na mesma
  collection `legal_chunks` via `load_indexable_chunks()`. Idempotente por `chunk_id`
  (point id = uuid5 no Qdrant; dict-key no InMemory).
- **`packages/rag/retriever.py`** — `SeparatedRetrieval{statutes, case_law}` +
  `LegalRetriever.retrieve_separated()`: duas recuperações independentes filtradas por
  `doc_type` (statute / case_law), cada bloco ranqueado e truncado a `top_k` por conta
  própria. `_with_doc_type` injeta o filtro sem mutar o request original.
- **`packages/rag/search_service.py`** — `search_separated()` + `_build_query()`
  (dedup do mapeamento request→`RetrievalQuery`).
- **`apps/api/routes/search.py`** — `SearchRequest.separate: bool=False`;
  quando `true`, a resposta carrega `separated: {statutes[], case_law[]}` além de
  `results`. Cada hit já carrega `citation.doc_type` (statute|case_law). Rota só delega.
- **`packages/embeddings/fake_provider.py`** — sinônimos para tornar o seed de
  jurisprudência recuperável por queries consumeristas (cdc→consumidor, banco/
  financeiro/financeira→financeira, instituicao/instituico→instituicao, aplica/
  aplicavel→aplicacao). NÃO afeta os casos Fase 3 (defeito/arrependimento intactos).
- **`apps/worker/jobs/search_demo.py`** — indexa ambos; statute queries filtradas a
  `doc_type=statute`; bloco separado novo provando Súmula 297 no case_law.

## Como indexar statute + case_law

```bash
make ingest-cdc                                  # -> data/generated/cdc_chunks.jsonl
python -m apps.worker.jobs.ingest_case_law       # -> data/generated/case_law_chunks.jsonl
make index-cdc                                   # indexa AMBOS em legal_chunks (Qdrant)
make search-demo                                 # prova offline (fake provider)
```

> PENDÊNCIA para o FoundationAgent (Makefile, fora do meu ownership): criar
> `make ingest-case-law` (`python -m apps.worker.jobs.ingest_case_law`). O alvo
> `make index-cdc` já passa a indexar `case_law_chunks.jsonl` quando presente — sem
> mudança de Makefile necessária para a indexação. Sem o JSONL de jurisprudência,
> `load_case_law_chunks()` retorna vazio e nada de case_law é indexado (§22).

## Prova de separação + não-regressão (`make search-demo`, saída real)

```text
[OK] statute query='defeito do produto' -> art. 12        (art.12 score=0.421 topo)
[OK] statute query='direito de arrependimento ...' -> 49   (art.49 score=0.391 topo)
[OK] statute query='prazo para reclamar de vício' -> 26    (art.26 score=0.449 topo)
[OK] separated query='CDC aplica-se a banco e instituição financeira' -> stj-sumula-297
        statutes:  art.6º / art.18 / art.12
        case_law:  stj-sumula-297 score=0.730  stj-sumula-479 0.434  stj-sumula-543 0.221
All acceptance queries passed.
```

Aceite §22: busca separa statute de case_law; jurisprudência só aparece com fonte
indexada (bloco case_law vazio quando o JSONL não foi gerado —
`test_case_law_block_empty_without_source`). Súmula 297 lidera o bloco case_law,
refletindo a autoridade 0.88.

## Testes (offline, fakes/InMemoryVectorStore)

- `tests/unit/rag/test_retriever_separation.py` (novo): (a) `doc_type=case_law` →
  só súmulas; (b) `doc_type=statute` → só artigos do CDC; (c) query consumerista sem
  filtro → ambos os blocos com `doc_type` identificável; (d) sem fonte → case_law vazio;
  + autoridade STJ súmula = 0.88.
- `tests/integration/test_search.py`: novos `test_search_filter_case_law_returns_only_case_law`,
  `test_search_filter_statute_excludes_case_law`, `test_search_separated_blocks`
  (substituem o antigo `test_search_filter_by_doc_type`, que assumia ausência de
  jurisprudência). Fixtures de seed estendidas com Súmula 297.
- `tests/unit/conftest.py`: fixture `case_law_chunks` (Súmulas 297/479, payload §9 em
  `metadata`).

```bash
make test  -> 125 passed
make lint  -> ruff: All checks passed ; mypy: Success, 69 files
```

Não-regressão Fase 3 confirmada: `test_retriever.py` e `test_search.py`
(defeito→12, arrependimento→49) passam; demo statute idem.

## Contrato para o `answer` (como consumir os blocos)

O retriever expõe **dois caminhos** — o answer escolhe:

1. **Flat + filtro**: `SearchService.search(query, top_k, filters={"doc_type": "statute"})`
   ou `{"doc_type": "case_law"}` → `list[RetrievedChunk]` só daquele tipo.
2. **Blocos**: `SearchService.search_separated(query, top_k, filters?) -> SeparatedRetrieval`
   (`packages/rag/retriever.py`), com `.statutes: list[RetrievedChunk]` e
   `.case_law: list[RetrievedChunk]`, cada bloco já ranqueado/truncado a `top_k`.

Cada `RetrievedChunk.citation.doc_type` identifica a origem; metadados de citação de
jurisprudência (court, case_number, precedent_type, is_binding, datas, source_url)
estão em `RetrievedChunk.metadata`. Para o AnswerWriter renderizar §32: "Fundamento
legal" ← `statutes`; "Jurisprudência relevante" ← `case_law` (omitir o bloco quando
vazio — nunca inventar súmula, §22). `case_law` permanece `[]` quando nenhuma fonte
de jurisprudência foi recuperada.

Nenhuma mudança no shape de `RetrievedChunk`/`CitationRef` (já carregavam `doc_type`).
A novidade é o agregado `SeparatedRetrieval` e o flag `separate` no `/search`.
