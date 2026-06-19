# Fase 2 — SCHEMAS (legal-domain) — summary

## Arquivos criados

- `packages/legal_types/__init__.py` — reexporta enums + schemas.
- `packages/legal_types/enums.py` — DocType, LegalArea, Source, Jurisdiction, PrecedentType, SupportLevel, NormType (StrEnum).
- `packages/legal_types/schemas.py` — SourceMetadata, LegalDocument, LegalChunk, LegalCitation, CaseLawDocument (Pydantic v2).
- `packages/legal_types/citations.py` — slugify, build_chunk_id, citation_from_chunk, citation_from_case_law, format_citation.
- `packages/legal_types/hierarchy.py` — AuthorityTier, AUTHORITY_WEIGHTS (§39), tier_for_statute/case_law, authority_weight_*.
- `packages/legal_types/temporal_validity.py` — parse_version_date, is_current, current_chunks, select_version_at, latest_version.
- `tests/unit/legal_types/test_schemas.py`, `test_enums.py`, `test_citations.py`, `test_hierarchy.py`, `test_temporal_validity.py`.
- `_workspace/CONTRACTS.md` — criado (não existia); shapes completos para consumidores.

## Campos dos schemas (para ingestion consumir)

Campos mínimos EXATOS de §8 — ver CONTRACTS.md. Pontos para ingestion:
- `LegalChunk` carrega todos os campos do documento + `chunk_id, article, paragraph, inciso, alinea, text`.
  `text` tem `min_length=1`. Defaults: `country="BR"`, `metadata={}`.
- `chunk_id` deve vir de `build_chunk_id(...)` (determinístico → idempotência §40.4): `cdc-8078-1990-art-12`.
- `content_hash` no formato `sha256:<hex>`.
- Payload RAG (§9): `is_current`/`version` em statute, `precedent_type`/`is_binding` em case_law.
  Enums serializam como string (StrEnum), compatível com payload Qdrant.
- `CaseLawDocument.doc_type` é `Literal[DocType.CASE_LAW]` (não setar manualmente outro valor).

## Saída real

### make test

```bash
pytest
..............................                                           [100%]
30 passed, 1 warning in 0.15s
```
(1 warning: StarletteDeprecationWarning do FastAPI TestClient — herdado da Fase 1, fora do ownership.)

### make lint

```bash
ruff check .
All checks passed!
mypy packages apps
Success: no issues found in 17 source files
```

## Pendências / notas para o orquestrador

- `make lint` roda mypy apenas em `packages apps` (config Fase 1) — `tests/` não é type-checked.
  Não alterei pyproject (fora do meu ownership). Os testes usam anotações corretas mesmo assim.
- Consumidores a revalidar quando integrarem: **ingestion** (constrói LegalChunk/chunk_id/payload §9),
  **storage** (payload Qdrant a partir dos schemas), **retrieval** (filtros por enums + legal_authority via hierarchy),
  **answer** (LegalCitation/format_citation), **agentic** (RetrievedSource referenciam chunk_id).
- `Jurisdiction` e `NormType` enums foram adicionados como vocabulário fechado útil, mas os campos
  `jurisdiction`/`norm_type` nos schemas permanecem `str | None` conforme §8 (não restringi para manter
  os campos mínimos EXATOS). Ingestion pode normalizar contra os enums.
