# Fase 2 — INGESTÃO (ingestion) — summary

Reexecução v0.2. Consome os schemas de `packages/legal_types/` (não alterados).
Fronteira com o indexador = JSONL; nenhum embedding/Qdrant aqui.

## Arquivos criados (ownership)

- `packages/ingestion/__init__.py`
- `packages/ingestion/loaders/__init__.py`
- `packages/ingestion/loaders/base.py` — `RawDocument` (dataclass de provenance) + `DocumentLoader` (Protocol).
- `packages/ingestion/loaders/local_markdown.py` — `LocalMarkdownLoader` + `parse_front_matter` (bloco de provenance em comentário HTML no topo do .md; chaves obrigatórias sem default).
- `packages/ingestion/normalizer.py` — `normalize_text` determinístico (NFC, CRLF→LF, NBSP, whitespace, blank lines). Conservador: não altera o texto normativo.
- `packages/ingestion/versioning.py` — `content_hash` (`sha256:<hex>`), `hash_for_raw`, `deduplicate_by_hash` (idempotência por hash).
- `packages/ingestion/chunker.py` — `chunk_document` / `iter_article_sections`. Parser por estrutura normativa: detecta cabeçalho `## Art. N` (inclui `6º`, `14-A`), isola cada artigo preservando §/incisos/alíneas no `text`. `chunk_id` estável via `build_chunk_id`; `article` renderizado (`6º`/`12`).
- `apps/worker/jobs/ingest_cdc.py` — job `make ingest-cdc`: load → chunk → dedup por hash → JSONL ordenado por `chunk_id`, `created_at` fixo (byte-stable).
- `data/seed/cdc/cdc.md` — seed do CDC, arts. 6º/12/14/18/26/49.
- `tests/unit/ingestion/` — `test_normalizer.py`, `test_versioning.py`, `test_chunker.py`, `test_local_markdown.py`, `test_ingest_cdc.py` (todos offline; sem rede).

## Origem do texto do cdc.md

Download **bem-sucedido** do Planalto via `curl` (sandbox desabilitado só para o download; HTML em ISO-8859-1, 200 KB):
`https://www.planalto.gov.br/ccivil_03/leis/l8078.htm`. HTML convertido para UTF-8, tags removidas, e os 6 artigos extraídos na **redação vigente**. Anotações de tramitação ("Redação dada por", "Incluído pela Lei", "Vigência") e redações superadas foram removidas; art. 6º inclui incisos XI–XIII (Lei 14.181/2021) e o inciso III na redação atual. Front-matter marca `source=planalto`, `source_url`, `norm=Lei 8.078/1990`, `version=2026-06-16`. Sem dados pessoais nem processos sigilosos (§40.7).

## Chunks por artigo (6 chunks, 1 por artigo)

| chunk_id | article | content_hash (prefixo) | len(text) |
|---|---|---|---|
| cdc-8078-1990-art-6  | 6º | sha256:1eed5898ca45bfce… | 2355 |
| cdc-8078-1990-art-12 | 12 | sha256:e050cfc4957584d2… | 1113 |
| cdc-8078-1990-art-14 | 14 | sha256:583e3638ce7c5681… | 941  |
| cdc-8078-1990-art-18 | 18 | sha256:6121ab2f1575dfe7… | 2395 |
| cdc-8078-1990-art-26 | 26 | sha256:352451bb9025daf9… | 794  |
| cdc-8078-1990-art-49 | 49 | sha256:71a13beb1f38df89… | 529  |

Metadata por chunk: `doc_type=statute`, `source=planalto`, `legal_area=consumer`, `jurisdiction=federal`, `norm_type=lei`, `norm_number=8078`, `norm_year=1990`, `version=2026-06-16`, `source_url`, `content_hash`, `metadata.is_current=true`.

## Amostra (1 linha do JSONL — art. 49)

```json
{"chunk_id": "cdc-8078-1990-art-49", "document_id": "cdc-8078-1990", "doc_type": "statute", "source": "planalto", "title": "Código de Defesa do Consumidor (Lei nº 8.078/1990)", "legal_area": "consumer", "country": "BR", "jurisdiction": "federal", "norm_type": "lei", "norm_number": "8078", "norm_year": "1990", "article": "49", "paragraph": null, "inciso": null, "alinea": null, "text": "## Art. 49\n\nO consumidor pode desistir do contrato, no prazo de 7 dias...", "source_url": "https://www.planalto.gov.br/ccivil_03/leis/l8078.htm", "version": "2026-06-16", "content_hash": "sha256:71a13beb1f38df89ce702527f9aa6b2f24a4a524b622127035b70d4740868534", "created_at": "2026-06-16T00:00:00Z", "metadata": {"is_current": true}}
```

## Prova de idempotência

`make ingest-cdc` rodado 2x; `shasum` do JSONL idêntico:
```text
RUN1: adbe3ad440bb8ca3df13948af74b4856964b5faf  data/generated/cdc_chunks.jsonl
RUN2: adbe3ad440bb8ca3df13948af74b4856964b5faf  data/generated/cdc_chunks.jsonl
```
6 chunks em ambas; dedup por `content_hash` (`deduplicate_by_hash`) + `created_at` fixo no job → saída byte-stable. Normalização determinística garante hash estável (testado em `test_normalizer.py`/`test_versioning.py`).

## Saída real

### make ingest-cdc

```text
Ingested 6 chunk(s) from .../data/seed/cdc/cdc.md
Articles detected: 6º, 12, 14, 18, 26, 49
Wrote .../data/generated/cdc_chunks.jsonl
```

### make test

```text
51 passed, 1 warning in 0.14s
```
(1 warning: StarletteDeprecationWarning do FastAPI TestClient — herdado da Fase 1, fora do ownership.)

### make lint

```bash
ruff check .  -> All checks passed!
mypy packages apps -> Success: no issues found in 25 source files
```

## Notas para consumidores (retrieval / storage)

- O JSONL é o contrato: 1 `LegalChunk` por linha, ordenado por `chunk_id`. Payload §9 derivável direto (`is_current` em `metadata`, `version` no chunk). `content_hash` no formato `sha256:<hex>`.
- O `text` do chunk **inclui** a linha de cabeçalho `## Art. N` (preserva o marcador de artigo p/ `exact_citation_match`). Se retrieval preferir texto sem heading, sinalizar via CONTRACTS — é mudança de 1 linha no chunker, não no shape.
- Granularidade atual = artigo. `paragraph/inciso/alinea` ficam `null` (campos disponíveis para chunking mais fino futuro sem quebrar ids existentes).
- `data/generated/*` é gitignored exceto `.gitkeep` (verificado).

## Pendências

Nenhuma. Download do Planalto OK; 6 artigos detectados; idempotência comprovada; test/lint verdes.
Jurisprudência (Fase 6, `doc_type=case_law`) não faz parte desta fase.
