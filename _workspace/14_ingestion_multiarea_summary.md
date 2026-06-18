# Fase B — Ingestão integral multi-área (7 códigos federais núcleo)

Dono: ingestion. Depende da Fase A (legal-domain): `NormType.decreto_lei`.

## 1. Vendoring (Planalto → `data/seed/<area-código>/_source/`)

Cada HTML cru vendado com `MANIFEST.md` (URL + sha256 + size). 6 de 7 URLs do escopo
vieram diretas; **1 correção de URL** registrada abaixo. Nenhuma falha de Cloudflare/404 não
resolvida — **sem lacuna de conteúdo**.

| código | norm_type | legal_area | norm | arquivo vendado | sha256 (HTML) |
|--------|-----------|------------|------|------------------|---------------|
| CF/88 | constituicao | constitutional | 1988 | `data/seed/constitucional/_source/planalto_constituicao.html` | `299f5441c0b7…` |
| CC | lei | civil | 10406/2002 | `data/seed/civil_cc/_source/planalto_l10406compilada.html` | `4c3f81f6f721…` |
| CP | decreto_lei | criminal | 2848/1940 | `data/seed/criminal_cp/_source/planalto_del2848compilado.html` | `abb194de016b…` |
| CLT | decreto_lei | labor | 5452/1943 | `data/seed/labor_clt/_source/planalto_del5452compilado.html` | `4a549cb45e20…` |
| CTN | lei | tax | 5172/1966 | `data/seed/tax_ctn/_source/planalto_l5172compilado.html` | `23956cbdedfe…` |
| CPC | lei | civil | 13105/2015 | `data/seed/civil_cpc/_source/planalto_l13105.html` | `ab8067fdfe71…` |
| CPP | decreto_lei | criminal | 3689/1941 | `data/seed/criminal_cpp/_source/planalto_del3689compilado.html` | `b8a1480058d2…` |

Hash completo e URL em cada `_source/MANIFEST.md`. O sha256 também é pinado no frontmatter
do seed `.md` gerado (`fonte_html_hash`), fechando a cadeia de proveniência (§40.4).

### Correção de URL (CC)
A URL do escopo `…/_ato2002-2006/2002/lei/l10406compilada.htm` retorna **HTTP 404**. A URL
canônica do Planalto para o CC compilado é
`https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm` (verificada, HTTP 200,
924 KB). Adotada e registrada em `codes.py` + MANIFEST. Não inventei fonte (§2).

### Lacunas
Nenhuma. Os 7 códigos foram vendados integralmente.

## 2. Loader determinístico (generalizado, não reescrito)

`packages/ingestion/loaders/planalto_html.py` (loader da Fase 13) **generalizado**, não
reescrito:
- novo `SeedSpec` (frontmatter por código); `build_seed_markdown(html_path, spec=None)` —
  sem `spec` mantém o CDC (compatível com `ingest_cdc`).
- removido dead code (`_PUBLICATION_RE` hardcoded do CDC).
- **fix de fidelidade**: páginas como o CTN quebram `Art.\n1º` num `<br>`; `_ART_LINEBREAK_RE`
  junta marcador+número antes da detecção. Sem isso, arts 1–3 do CTN eram silenciosamente
  engolidos como corpo (perda de conteúdo). Corrigido.

Conversão HTML→md inalterada no corpo (latin-1, `## Art. N` por artigo, §/inciso/alínea
preservados). Determinística e pura.

## 3. Chunking artigo-a-artigo

Mesma granularidade do CDC integral (`chunk.text` inclui o heading `## Art. N`; metadata
jurídica completa: `legal_area`, `norm_type` incl. `decreto_lei`, `norm_number`, `norm_year`,
`source=planalto`, `source_url`, `version=compilado`, `content_hash=sha256:…`, `ingested_at`
fixo `2026-06-18`, `metadata.is_current=True`).

### Fix de colisão de chunk_id (crítico)
Códigos reiniciam numeração entre divisões estruturais (CF/88 corpo permanente × ADCT;
disposições transitórias). O mesmo `Art. N` recorre com **texto diferente**. Como o
indexador usa `uuid5(chunk_id)` como point id, a colisão **sobrescreveria** silenciosamente
um artigo distinto. Antes do fix: **172 chunk_ids duplicados** (160 só na CF/88).
Solução determinística em `chunker.py`: a 1ª ocorrência mantém o id canônico, repetições
ganham sufixo estável `-occ-K` por ordem de documento. Display `article` inalterado
("Art. 1º" continua "Art. 1º"). Pós-fix: **6169 ids únicos, 0 colisões**.

## 4. Contagem de chunks por código

`make`/`python -m apps.worker.jobs.ingest_codes`:

| código | chunks |
|--------|-------:|
| cf88 | 514 |
| cc | 2083 |
| cp | 423 |
| clt | 1014 |
| ctn | 209 |
| cpc | 1080 |
| cpp | 846 |
| **total** | **6169** |

Distribuição por área: civil 3163, criminal 1269, labor 1014, constitutional 514, tax 209.
Por norm_type: lei 3372, decreto_lei 2283, constituicao 514. Geração <1 s; ~7.2 MB.

## 5. Job / JSONL / shape

- Novo job: `apps/worker/jobs/ingest_codes.py` → **um único** `data/generated/statutes_chunks.jsonl`.
- **Decisão (1 arquivo multi-área):** o consumidor de indexação (`chunk_jsonl.load_indexable_chunks`)
  concatena JSONLs na collection única `legal_chunks`, e `legal_area` é chave filtrável
  (`FILTERABLE_KEYS`). Um arquivo multi-área casa diretamente com esse consumo e evita 7
  caminhos de carga. Shape: **um `LegalChunk` por linha** (idêntico ao `cdc_chunks.jsonl`),
  ordenado por `chunk_id`, com `\n` final → byte-estável.
- Streaming por código (`iter_all_chunks`): pico de memória = um código por vez; dedup global
  por `content_hash` num único `set`.
- `ingest_cdc` **intacto** (130 chunks, arts 6/12/14/18/26/49 detectados). Único efeito colateral:
  o H1 do `cdc.md` passou a refletir `spec.title` (cosmético, no preâmbulo ignorado pelo chunker);
  `cdc_chunks.jsonl` **não muda** (hashes idênticos).
- Registry: `packages/ingestion/codes.py` (`CORE_CODES`, `CodeEntry`, `SeedSpec`).

## 6. Idempotência (comprovada)

- 2 execuções → `statutes_chunks.jsonl` **byte-idêntico** (sha256
  `7f6bc33b8ac1…`, igual nas duas rodadas).
- Dedup por `content_hash` global; ids únicos e estáveis (incl. desambiguação `-occ-K`).
- Teste `test_idempotent_byte_stable` + `test_disambiguation_is_idempotent`.

## 7. Coordenação pendente (não editei fora de ownership)

- **FoundationAgent (Makefile):** adicionar target
  `ingest-codes: $(COMPOSE_LOCAL) exec -T api python -m apps.worker.jobs.ingest_codes`
  (e incluí-lo no fluxo `seed`/bootstrap). Hoje roda standalone via `python -m`.
- **retrieval (chunk_jsonl.py / index_cdc.py):** incluir `statutes_chunks.jsonl` em
  `load_indexable_chunks()` para indexar o corpus multi-área na collection `legal_chunks`.
  Arquivo é gitignored (`data/generated/*`), regenerável pelo job — fronteira §12.9 mantida.
- **legal-domain:** nenhuma extensão de schema necessária — `LegalChunk`/`SourceMetadata` e
  `NormType.decreto_lei` (Fase A) já cobrem tudo.

## 8. Lint / testes (resultado real)

- `ruff check .` → **All checks passed!** (inclui C90 ≤ 10).
- `mypy packages apps` → **Success: no issues found in 96 source files**.
- `pytest tests/unit/ingestion/` → 43 passed.
- `pytest` (suíte completa) → 212 passed (1 warning de deprecation do Starlette/httpx, alheio).

## Arquivos
- `packages/ingestion/codes.py` (novo) — registry dos 7 códigos.
- `packages/ingestion/loaders/planalto_html.py` — `SeedSpec` + fix `Art.\nN`.
- `packages/ingestion/chunker.py` — desambiguação `-occ-K` de chunk_id.
- `apps/worker/jobs/ingest_codes.py` (novo) — job multi-área.
- `tests/unit/ingestion/test_ingest_codes.py` (novo), `test_chunker.py` (+2 testes).
- `data/seed/{constitucional,civil_cc,criminal_cp,labor_clt,tax_ctn,civil_cpc,criminal_cpp}/_source/`
  — HTML vendado + `MANIFEST.md`; seeds `.md` regenerados pelo job.
- `data/seed/cdc/_source/MANIFEST.md` (novo, retroativo p/ consistência).
