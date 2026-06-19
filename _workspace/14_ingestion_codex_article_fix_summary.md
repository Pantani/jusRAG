# Fase 14 — Codex fix: campo `article` dotless para match de citação (CC/CPC ≥1000)

Dono: ingestion. Escopo: `packages/ingestion/chunker.py` + `data/generated/*.jsonl` + testes.

## 1. Bug confirmado (Opção A aplicada)

O fix anterior do separador de milhar gravava `article` com ponto de display (`"1.238"`), por
fidelidade de citação. Mas o caminho de ranking/filtro compara **dotless**:

- `packages/rag/query_analyzer.py:extract_article` — regex `(\d+)`: `"art 1238"` → `"1238"`;
  `"art. 1.238"` → `"1"` (captura só os dígitos antes do ponto).
- `packages/rag/legal_ranker.py:exact_citation_match` — compara `payload["article"]` **literal**
  contra esse valor.

Consequência: com `article="1.238"`, nenhuma query casava ("1238" ≠ "1.238", "1" ≠ "1.238") →
artigos altos de CC (≥1.000) e CPC nunca recebiam o boost `exact_citation_match` nem casavam filtro
de artigo. Regressão de recuperação em toda a faixa alta. Confirmado lendo os dois consumidores.

## 2. Correção (origem, sem tocar retrieval)

`packages/ingestion/chunker.py`:
- `_render_article` → renomeado `_match_article`. Agora produz o **token canônico dotless**:
  remove o separador de milhar (`"1.238"` → `"1238"`), preserva o ordinal 1–9 (`"6"` → `"6º"`) e o
  sufixo de letra (`"1.240-A"` → `"1240-A"`). Não reaplica mais o agrupamento de milhar.
- Removida a constante `_THOUSANDS_LIMIT` (não há mais re-pontuação).
- Docstring do módulo reescrita: `article` é o **match token** (consumido por
  `extract_article`/`exact_citation_match`); a superfície de citação legível com ponto
  (`## Art. 1.238`) vive no `text` renderizado (heading), preservada pelo loader e por
  `normalize_text`. `_id_article` já era dotless — inalterado.

Nenhum consumidor de ranking precisou mudar (objetivo da Opção A).

## 3. Como o campo `article` ficou

| número (fonte) | `article` (MATCH) | heading em `text` (DISPLAY) | chunk_id |
|---|---|---|---|
| Art. 6º (CDC) | `6º` | `## Art. 6º` | `…-art-6` |
| Art. 12 | `12` | `## Art. 12` | `…-art-12` |
| Art. 1.238 (CC) | `1238` | `## Art. 1.238` | `cc-10406-2002-art-1238` |
| Art. 1.240-A | `1240-A` | `## Art. 1.240-A` | `…-art-1240-a` |
| Art. 1337 / 1.337 (CC) | `1337` (convergem) | conforme fonte | `…-art-1337` |

## 4. Idempotência / reingestão (novos hashes)

- `data/generated/statutes_chunks.jsonl` regenerado: 2 execuções → sha256 idêntico
  **`e3ae1ce19f5c23a18ce49dfae37209eca3ec80c2d61afb907cb7c76b21ce0b57`** (era
  `31a1fbf0…`; mudou porque os `article` de CC/CPC ≥1000 perderam o ponto e o `content_hash`
  por-chunk não muda — só a serialização do campo `article`). 0 tokens `article` com ponto.
  chunk_ids inalterados (já eram dotless) — nenhum id existente quebrou.
- `data/generated/cdc_chunks.jsonl`: regenerado, sha
  `8cc6c7175f74fa2759e4cbc3509129f238c18642f3326972e8dd271bf88cd087`. CDC não usa milhar →
  `article` e `content_hash` por-chunk inalterados; arts. 6º/12/14/18/26/49 detectados.
- Reindex offline não necessário; bastou regenerar o JSONL (fronteira com o indexador).

## 5. Testes

`tests/unit/ingestion/test_chunker.py` (+2):
- `test_thousands_article_is_dotless_match_token_with_dotted_heading`: CC art. 1.238 →
  `article == "1238"`, `1.240-A` → `"1240-A"`, e `"## Art. 1.238" in text`.
- `test_thousands_article_matches_ranker_citation_path`: importa `packages.rag` (importar não é
  editar) e afirma o contrato fim-a-fim — `extract_article("art 1238") == "1238"` e
  `exact_citation_match(payload, "1238") == 1.0`. Também documenta honestamente que
  `extract_article("art. 1.238")` retorna `"1"` e por isso **não** casa (limitação do lado retrieval,
  ver §6).

Ajustados (semântica antiga dotted → nova dotless):
- `tests/unit/ingestion/test_code_article_coverage.py`: landmarks CC/CPC agora dotless
  (`1000/1511/1711/1784/2046`, `1000/1072`). `test_cc_reaches_full_range` inalterado (já fazia
  `re.sub(r"\D","")`).
- `tests/unit/ingestion/test_planalto_html_loader.py::test_thousands_separator_articles_are_captured`:
  afirma `article` dotless (`999/1000/1711/1337/2046`) E o ponto preservado no `text`
  (`## Art. 1.000`, `## Art. 2.046`).

## 6. O que retrieval precisa ratificar (NÃO editei — fora do meu ownership)

`extract_article` (`packages/rag/query_analyzer.py:17`, regex `\bart(?:igo|\.)?\s*(\d+)`) captura
só os dígitos antes do ponto: `"art. 1.238"` → `"1"`. Com o meu fix, queries **sem** ponto
(`"art 1238"`) passam a casar perfeitamente. Mas queries **com** ponto de milhar
(`"art. 1.238"`) ainda extraem `"1"` e não casam — agora é o único elo dotted remanescente, e do
lado retrieval. Recomendo a retrieval estender a regex para absorver o separador, ex.:
`(\d[\d.]*(?:-[A-Z])?)` seguido de `.replace(".","")` no retorno, espelhando a normalização do
chunker. Sem isso, a cobertura de exact-match fica restrita a queries dotless (que são as mais
comuns digitadas). Decisão e edição cabem a retrieval/legal-domain.

## 7. Lint / testes (real)

- `ruff check packages/ingestion apps/worker/jobs tests/unit/ingestion` → **All checks passed!** (C90 ≤ 10).
- `mypy packages apps` → **Success: no issues found in 97 source files**.
- `pytest tests/unit/ingestion/ tests/unit/rag/test_legal_ranker.py` → **62 passed**.

## Arquivos tocados
- `packages/ingestion/chunker.py` — `_render_article`→`_match_article` (dotless), docstring, call site.
- `tests/unit/ingestion/test_chunker.py` (+2 testes).
- `tests/unit/ingestion/test_code_article_coverage.py` (landmarks dotless).
- `tests/unit/ingestion/test_planalto_html_loader.py` (assert dotless + dotted heading no text).
- `data/generated/{statutes_chunks,cdc_chunks}.jsonl` regenerados (gitignored).
