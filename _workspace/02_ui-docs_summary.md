# Fase 2 — DOCS (ui-docs) — summary

## Arquivos tocados

- `docs/architecture.md` — adicionada seção "Pipeline de ingestão" (loader → normalizer → chunker por artigo → versioning/content_hash → JSONL) e "Schemas de domínio (§8)" (LegalDocument, LegalChunk, LegalCitation, CaseLawDocument; chunk_id determinístico; payload §9 deriva dos schemas; authority em hierarchy.py, vigência em temporal_validity.py).
- `docs/source-policy.md` — adicionada seção "CDC seed (Lei 8.078/1990)": fonte Planalto, arts. 6º/12/14/18/26/49, persistência source+source_url+norm_*+version+content_hash, chunk_id determinístico e idempotência por hash.
- `docs/legal-rag-design.md` — chunking estrutural referencia o pipeline e os campos de metadata jurídica do LegalChunk (§8) que viram payload §9 e alimentam legal_authority.
- `README.md` — nota de status atualizada para v0.2.

## Reinvocação (2026-06-16): ingestão funcional

IngestionAgent entregou e `make ingest-cdc` agora roda: gera `data/generated/cdc_chunks.jsonl` com 6 chunks (arts. 6º/12/14/18/26/49 da Lei 8.078/1990, redação vigente do Planalto), idempotente por `content_hash` sha256, JSONL casando com LegalChunk (§8/§9).

Mudança aplicada (só a seção de status do README):
- README: status v0.2 virou de "em finalização / ainda não executável" → **funcional**; `make ingest-cdc` adicionado à lista de alvos funcionais hoje. `index-cdc`/`search-demo`/`ask-demo`/`eval` seguem como fases 3+.
- `docs/source-policy.md` e `docs/architecture.md` já descreviam o pipeline (chunking por artigo, content_hash, idempotência) como implementado — nenhum ajuste necessário, já fiéis ao estado em disco.

## Não toquei

código, schemas, ingestion, Makefile, pyproject (fora do ownership).
