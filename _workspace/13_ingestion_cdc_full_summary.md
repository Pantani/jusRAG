# Fase 13.A.1 — CDC integral via Planalto HTML

## Fonte vendored

- URL: `https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm`
- Arquivo: `data/seed/cdc/_source/planalto_l8078compilado.html` (165 KB, ISO-8859-1)
- SHA256: `4aa899f6e9aa042f24be222e4e32cabff347cc25c1e317bc5dd6afcdd9642d76`
- Comando: `curl -sSL -A "Mozilla/5.0 (jusrag-brasil-ingestor)" <url> -o <path>` (única chamada de
  rede autorizada).
- O hash é gravado no frontmatter de `cdc.md` como `fonte_html_hash:` para auditoria (§2 / §40.4).

## Loader

`packages/ingestion/loaders/planalto_html.py` — conversor HTML→markdown stdlib-only
(`html.parser`), determinístico:

- Extrai `<p>` em ordem, distinguindo `centered` (cabeçalhos estruturais) de texto corrido.
- Emite `## Art. N` por artigo (forma `6º` para 1-9, `12`, `42-A`, `54-G`, etc.) — formato que o
  chunker existente já consome sem mudanças.
- Preserva integralmente §, incisos, alíneas e marcações de tramitação ("Redação dada por…",
  "Vigência", "Vide", `(Vetado)`) — nada é removido.
- Cabeçalhos `TÍTULO/CAPÍTULO/SEÇÃO/SUBSEÇÃO` viram `#`/`###`/`####` (acima de `##`, não interferem
  no chunker).
- Frontmatter compatível com `LocalMarkdownLoader`: `short_name`, `title`, `source: planalto`,
  `source_url`, `norm_type/number/year`, `version: compilado`, `legal_area: consumer`,
  `jurisdiction: federal`, `fonte_html_hash`.

## Pipeline

`apps/worker/jobs/ingest_cdc.py` agora:

1. Se `data/seed/cdc/_source/planalto_l8078compilado.html` existir, `main()` regenera `cdc.md` a
   partir do HTML antes de chunkar (idempotente).
2. `run(...)` aceita `html_path` (default `None`) — chamadores de teste passam `None` e fornecem o
   próprio `seed_path`, preservando isolamento.
3. Mantém timestamp fixo `2026-06-16` e dedup por `content_hash` (§40.4).

## Validações

- `make ingest-cdc`: 130 chunks gerados, artigos detectados de 1º a 119 (incluindo 42-A, 54-A..G,
  104-A..C).
- Idempotência: 2 execuções consecutivas → `diff -q` vazio em `cdc.md` e `cdc_chunks.jsonl`.
- Tamanhos finais: `cdc.md` 2027 linhas; `cdc_chunks.jsonl` 130 linhas.
- Artigos do MVP ainda presentes: 6º, 12, 14, 18, 26, 49.
- `make lint`: ruff + mypy verdes (93 arquivos).
- `tests/unit/ingestion/`: 34/34 passam (inclui 6 novos testes do loader Planalto).

## Testes novos (loader)

`tests/unit/ingestion/test_planalto_html_loader.py` — 6 testes, fixture HTML latin-1 com 3 artigos
+ cabeçalho de capítulo:

- `test_html_to_markdown_emits_article_headers` — detecta `## Art. 1º/2º/3º`, header de capítulo,
  §, inciso, alínea.
- `test_html_to_markdown_is_deterministic` — duas conversões produzem bytes idênticos.
- `test_build_seed_markdown_pins_html_hash` — SHA256 do HTML aparece no frontmatter.
- `test_build_seed_markdown_idempotent`.
- `test_generated_markdown_chunks_through_existing_loader` — round-trip com
  `LocalMarkdownLoader` + `chunk_document`.
- `test_build_seed_markdown_requires_existing_file` — erro explícito se HTML ausente.

## Regressões esperadas (input para A.4)

A expansão de 6 → 130 chunks recalibra o universo de busca; 4 testes do eval suite ficaram abaixo
dos thresholds atuais (calibrados para 6 chunks):

| Teste | Métrica | Antes (threshold) | Agora |
|-------|---------|-------------------|-------|
| `tests/evals/test_retrieval_eval.py::test_recall_at_5_meets_threshold_on_seed` | `recall@5 ≥ 0.80` | passava | `0.7917` |
| `tests/evals/test_answer_eval.py::test_refusal_rate_meets_threshold_on_seed` | `refusal_when_no_source_rate ≥ 0.90` | passava | `0.0000` (modelo agora tem contexto adjacente para questões OOS) |
| `tests/evals/test_run_all.py::test_suite_passes_gate_on_seed` | gate `strict` agregado | passava | falha (puxado pelos dois acima) |
| `tests/evals/test_run_all.py::test_main_exits_zero_on_seed` | exit code 0 | passava | exit 1 (gate falhou) |

Hipóteses para A.4:

- `recall@5 = 0.7917` — chunks adjacentes (e.g. arts. 13, 15) agora competem por slot; provavelmente
  basta aumentar `top_k` no harness de eval ou reforçar `legal_ranker` (citation_match weight).
- `refusal_rate = 0.0` — o gold OOS provavelmente assumia que nenhum chunk casava; com 130 chunks o
  retriever sempre retorna algo. Solução típica: threshold de score mínimo no router OOS, ou
  recalibrar os exemplos OOS para ficarem distantes do corpus expandido.

Demais testes (`182/186`) passam. O suite de retrieval/answer/agentic não regrediu fora de
`tests/evals/`.

## Commits

1. `feat(corpus): vendored Planalto CDC HTML source (Lei 8.078/1990)` — apenas o HTML.
2. `feat(corpus): Planalto HTML→markdown loader for full CDC integral text` — loader, ajuste do job,
   `cdc.md` regenerado, testes.
