# Fase 6 (v0.6) — Ingestão de Jurisprudência STJ (lado IngestionAgent/CaseLawAgent)

## Seed — `data/seed/case_law/stj_consumer_seed.jsonl`

5 súmulas públicas reais do STJ em Direito do Consumidor (texto curto, público, sem
PII, sem processo sigiloso — regra §40). Enunciados fiéis ao texto oficial do STJ:

| Súmula | Enunciado (resumo) | Fonte (source_url) |
|--------|--------------------|--------------------|
| **297** | "O Código de Defesa do Consumidor é aplicável às instituições financeiras." | stj.jus.br revista/eletronica sumulas capSumula297.pdf |
| **302** | "É abusiva a cláusula contratual de plano de saúde que limita no tempo a internação hospitalar do segurado." | capSumula302.pdf |
| **130** | "A empresa responde, perante o cliente, pela reparação de dano ou furto de veículo ocorridos em seu estacionamento." | capSumula130.pdf |
| **479** | "As instituições financeiras respondem objetivamente pelos danos gerados por fortuito interno relativo a fraudes e delitos praticados por terceiros no âmbito de operações bancárias." | capSumula479.pdf |
| **543** | "Na hipótese de resolução de contrato de promessa de compra e venda de imóvel submetido ao CDC, deve ocorrer a imediata restituição das parcelas pagas pelo promitente comprador — integralmente (culpa do vendedor/construtor) ou parcialmente (culpa do comprador)." | capSumula543.pdf |

Todas: `court="STJ"`, `source="stj"`, `precedent_type="summary"`, `is_binding=false`
(súmula comum do STJ não é vinculante), `legal_area="consumer"`. Nenhum número de
súmula ou texto inventado.

## Arquivos criados (ownership)

- `data/seed/case_law/stj_consumer_seed.jsonl` — seed (5 entradas).
- `packages/ingestion/loaders/stj.py` — `StjCaseLawLoader.load() -> list[CaseLawDocument]`.
  Normaliza ementa (NFC/whitespace determinístico), deriva `document_id=slugify("STJ-sumula-<n>")`
  (ex.: `stj-sumula-297`), `case_number="Súmula <n>"`, `content_hash=sha256(ementa_normalizada)`.
  Datas via `date.fromisoformat` (sem fallback silencioso).
- `packages/ingestion/loaders/stf.py` — placeholder mínimo (`StfCaseLawLoader`, `NotImplementedError`),
  simetria para fase futura. Sem seed, sem lógica real.
- `packages/ingestion/chunker.py` — estendido: `chunk_case_law(doc) -> LegalChunk | None` e
  `chunk_case_law_documents(docs) -> list[LegalChunk]`. **Não quebra** o chunking de statute
  (caminho separado). Sem ementa → `None` (jurisprudência sem fonte não é emitida, §22).
- `apps/worker/jobs/ingest_case_law.py` — entrypoint `python -m apps.worker.jobs.ingest_case_law`
  → `data/generated/case_law_chunks.jsonl`. Mesmo shape `LegalChunk` JSONL do `ingest_cdc`.
- `tests/unit/ingestion/test_stj_loader.py` — 6 testes.

> Nenhum `make` target novo criado (ownership do Makefile é do FoundationAgent). Entrypoint
> documentado: `python -m apps.worker.jobs.ingest_case_law`. **Pendência para orquestrador**:
> adicionar `make ingest-case-law` ao Makefile e incluir `case_law_chunks.jsonl` no `index-cdc`
> (ou job `index-case-law`) na mesma collection `legal_chunks`.

## Shape do chunk de case_law (LegalChunk, doc_type=case_law)

O chunk de jurisprudência é um `LegalChunk` (consumível pelo indexer existente sem mudar schema):

- `chunk_id = document_id` (ex.: `stj-sumula-297`), `doc_type=case_law`, `source=stj`.
- `title="STJ Súmula <n>"`, `text=` ementa normalizada, `source_url=` PDF oficial STJ,
  `version=` ISO da `judgment_date`, `content_hash="sha256:…"`.
- `article/paragraph/inciso/alinea = None`, `legal_area=consumer`.
- Payload §9 (jurisprudência) em `metadata`: `court`, `case_number`, `rapporteur`, `panel`,
  `precedent_type`, `is_binding`, `judgment_date`, `publication_date`, `is_current=True`.
  → `chunk_to_payload` (storage) já projeta `doc_type` e `metadata`; nenhuma mudança em payload.py.

## Idempotência (prova)

`ingest_case_law` rodado 2×: arquivos byte-idênticos (`diff` → identical). Dedup por
`content_hash` (`deduplicate_by_hash`): seed com a mesma súmula duplicada colapsa para 1 chunk
(`test_idempotent_by_hash`). `created_at` fixo (2026-06-16) garante JSONL byte-estável.

## Validação (saída real)

- `python -m apps.worker.jobs.ingest_case_law` → `Ingested 5 case_law chunk(s)`,
  `Entries detected: Súmula 130, 297, 302, 479, 543`. 2ª execução byte-idêntica.
- Inspeção JSONL: `doc_type=case_law`, `court=STJ`, `source_url` presente (https://www.stj.jus.br/…),
  `precedent_type=summary`, `is_binding=False`.
- `pytest tests/unit/ingestion/test_stj_loader.py` → **6 passed**. Suite completa → **118 passed**.
- `ruff check packages apps tests` → **All checks passed**. `mypy packages apps` → **Success, 69 files**.
  Complexidade ≤ 10 (funções pequenas; sem C901).

> Nota de ambiente: `python -m pytest` é interceptado por um shim do sandbox ("Pytest: No tests
> collected"); rodar `./.venv/bin/pytest` diretamente coleta e executa normalmente.

## Contrato para retrieval (filtro doc_type=case_law)

- O retriever filtra jurisprudência via `filters={"doc_type": "case_law"}` (já em
  `FILTERABLE_KEYS` de `packages/storage/payload.py`). Statute: `{"doc_type": "statute"}`.
- Metadados de citação de jurisprudência (court, case_number, precedent_type, is_binding,
  datas, source_url) estão no `payload`/`metadata` do resultado — o answer monta o bloco
  "Jurisprudência relevante" a partir daí.
- **Não houve extensão de `schemas.py`** (CaseLawDocument já bastava). `CaseLawDocument` é o
  shape do loader; o chunk indexável é `LegalChunk(doc_type=case_law)` carregando o payload §9
  em `metadata` — decisão para não acoplar o indexer a um segundo tipo de chunk.
