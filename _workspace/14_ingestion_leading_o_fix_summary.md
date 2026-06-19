# Fase 14 — IngestionAgent: leading-"O" corruption + ordinal/test fixes

PR #3 CodeRabbit review, 4 itens em `packages/ingestion/` (+ `tests/integration/`).

## BUG 1 (CRÍTICO) — ordinal `[º°o]?` comendo o "O" maiúsculo do caput

`packages/ingestion/loaders/planalto_html.py`, `_ARTICLE_RE`.

Regex **antes**:
```
^\s*Art\.?\s*(\d[\d.]*(?:-[A-Z])?)\s*[º°o]?\s*(.*)        # re.IGNORECASE
```
Com `IGNORECASE`, `[º°o]?` casava o "O" maiúsculo inicial do corpo
("Art. 10. O fornecedor" → num `10.`, corpo `fornecedor`). Corrupção silenciosa
de conteúdo jurídico, já persistida nos 8 seeds.

Regex **depois** (sugestão CodeRabbit, validada):
```
^\s*Art\.?\s*(\d(?:[\d.]*\d)?(?:-[A-Z])?)(?:[º°]|(?-i:o))?\.?\s*(.*)   # re.IGNORECASE
```
`(?-i:o)` desliga IGNORECASE só para o `o` ASCII (ordinal "1o"), nunca o "O" de
início de frase. `\.?` consome um ponto final do marcador ("Art. 10.").

Casos validados (num, corpo):
| entrada | antes | depois |
|---|---|---|
| `Art. 10. O fornecedor` | `('10.', 'fornecedor')` ❌ | `('10', 'O fornecedor')` ✅ |
| `Art. 10º O produto` | `('10', 'O produto')` | `('10', 'O produto')` ✅ |
| `Art. 1o Esta lei` | `('1', 'Esta lei')` | `('1', 'Esta lei')` ✅ |
| `Art. 1.234. O material` | `('1.234.', 'material')` ❌ | `('1.234', 'O material')` ✅ |
| `Art. 5-A. O produto` | `('5-A', '. O produto')` ❌ | `('5-A', 'O produto')` ✅ |

### Impacto / artigos afetados (estimativa)
Headings com ponto-espúrio (`## Art. N.`) nos seeds versionados antes do fix: 4821.
Artigos cujo caput começava em minúscula (capital comido — "O"/"A"/"Os"/"As"): **~1117**
(cc 507, cpc 259, cpp 173, cf88 83, ctn 35, clt 34, cdc 24, cp 2).

### Regeneração
`make ingest-cdc` + `python -m apps.worker.jobs.ingest_codes` regeneraram os 8
seeds (`cdc.md` + cf88/cc/cp/clt/ctn/cpc/cpp) e os dois JSONL. Verificado:
`cdc.md` art. 10 agora abre com "O fornecedor"; caputs em minúscula caíram de
1117 → 14 (todos legítimos/pré-existentes: ordinal CC arts. 1-9 em `<sup>o</sup>`
em linha própria — defeito antigo e distinto, sem perda de conteúdo; faixas
"Art. N a Art. M" no CPP; cf88 art. 100 que começa em "à").

### SHAs (idempotente — idênticos em re-execução)
```
cdc.md               843aef20c995648e45e555972531833f100792f1030caf1dd70f326d06554e92
cdc_chunks.jsonl     6291d06cd438b3e7274cf470f6d2306ee0ecfe1345a3873cbb3d2c6419f11f61  (130 chunks)
statutes_chunks.jsonl 8d0498604dc50eec6030fb1ab1656a16b0ff720cabd279ad997d0ed356759261 (6169 chunks)
```
Contagens por código: cf88 514, cc 2083, cp 423, clt 1014, ctn 209, cpc 1080, cpp 846.
Arts. de aceite do CDC detectados: 6º, 12, 14, 18, 26, 49 (todos presentes).

## BUG 2 — ordinal renderizado depois do sufixo ("1-Aº" → "1º-A")

`chunker.py:_match_article` e `planalto_html.py:_format_article_line`.
Forma canônica: ordinal **antes** do hífen. "1-A"→"1º-A", "2-B"→"2º-B";
"42-A"→"42-A" e "10"→"10" (≥10 sem ordinal); "6"→"6º".

Efeito colateral necessário: a forma canônica `## Art. 5º-A` quebrava
`_ARTICLE_HEADING_RE` (que esperava ordinal no fim do token). A heading-regex foi
ajustada para capturar o ordinal **entre** o radical numérico e o sufixo
`(?P<num>\d[\d.]*(?P<ord>[ºo°]?)(?:-[A-Z])?)`; `_match_article`/`_id_article`
passam por `_strip_ordinal` antes de derivar token e id. Diff de chunk_ids/articles
contra a geração anterior: **0** — ids existentes preservados.

Teste novo: `tests/unit/ingestion/test_chunker.py::test_match_article_ordinal_before_letter_suffix`.

## BUG 3 — teste pesado fora de tests/unit

`git mv tests/unit/ingestion/test_code_article_coverage.py
tests/integration/test_code_article_coverage.py`. Carrega os HTML vendados
completos (~MB) dos 7 códigos — viola §8 (unit = seed pequeno). Mantida a
asserção de cobertura de faixa (CC 1784/2046, CPC 1072). Continua offline
(bytes vendados) e coletado por `make test`/CI: `pyproject.toml` tem
`testpaths = ["tests"]` e o CI roda `make test` → `pytest`. Nenhuma coordenação
de Makefile/CI necessária.

## BUG 4 — regressão do "O" inicial

`tests/unit/ingestion/test_planalto_html_loader.py`: adicionados
`test_leading_capital_o_is_preserved_in_caput` e
`test_leading_capital_o_preserved_through_chunk` (trava BUG 1 end-to-end: o "O"
chega ao `text` do chunk; "Art. 5-A" vira artigo "5º-A").

## Lint / testes (reais)

- `ruff check packages/ingestion apps/worker/jobs tests/unit/ingestion tests/integration/test_code_article_coverage.py` → **All checks passed** (C90 ok).
- `mypy packages/ingestion apps/worker/jobs` → **Success: no issues found in 21 source files** (strict).
- `pytest tests/unit/ingestion tests/integration/test_code_article_coverage.py` → **57 passed**.
- Suíte completa `pytest tests/` → **288 passed, 5 failed**.

### Sobre os 5 failures (FORA do meu ownership)
Todos em `tests/evals/` (gate de eval / golden dataset, owner = eval-agent):
`test_run_all`, `test_answer_eval`, `test_anti_overfit` (x2), e um caso de
síntese (ex.: CLT art. 816 agora REFUSED). Causa: a correção do BUG 1 mudou o
conteúdo de ~1117 caputs (content_hash + texto), deslocando o comportamento de
recuperação/síntese de algumas golden questions cujas expectativas foram
calibradas contra o texto **corrompido**. Não é quebra de contrato: CLT art. 816
continua presente e agora correto ("O juiz ou presidente manterá a ordem…").
Recalibração do golden/thresholds é item do eval-agent. Coordenar via
`legal-evals` antes do merge do PR #3.
