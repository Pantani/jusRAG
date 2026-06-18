# Fase B — Fix P1: CC truncado em ~art. 999 (separador de milhar)

Dono: ingestion. Escopo: `packages/ingestion/{loaders/planalto_html.py,chunker.py}` +
`data/generated/statutes_chunks.jsonl` + testes.

## 1. Causa-raiz (confirmada na fonte vendada)

A fonte vendada do CC (`data/seed/civil_cc/_source/planalto_l10406compilada.html`, 902 KB,
sha256 `4c3f81f6f721…`) está **íntegra**: contém `Art. 1.000`, `Art. 1.711`, `Art. 1.784`,
`Art. 2.046`. Não houve truncamento de curl — nada a revendar.

O bug era de **parsing**. O Planalto grafa artigos de 4 dígitos com **separador de milhar**
(`Art. 1.000.`, `Art. 1.711.`) e, de forma inconsistente, alguns **sem** ponto (`Art. 1337.`).
As regexes de detecção capturavam apenas `\d+`:

- `_ARTICLE_RE` (loader) e `_ARTICLE_HEADING_RE` (chunker) casavam só o `1` em `Art. 1.000`,
  emitiam token `1` e jogavam `.000. A sociedade…` como corpo.
- Como o chunker já desambigua `Art. N` repetido com sufixo `-occ-K`, **todos** os
  `Art. 1.NNN` viravam `cc-…-art-1-occ-K` — silenciosamente colados no artigo 1.
- Só os raros artigos sem ponto (`1337`) entravam corretos → "1000 distintos, máx 1337,
  lacuna 999→1337". A contagem de chunks (2083) mascarava o buraco porque o nº de seções
  no documento é o mesmo; só os tokens estavam errados.

Confirmação: `dotted-thousand Art` = 1076 ocorrências no CC, 77 no CPC, 0 nos demais — exatamente
os dois códigos afetados (CC parava em 1337, CPC em 999).

## 2. Fix (por princípio, sem hard-code de faixa)

- `_ARTICLE_RE` / `_ARTICLE_HEADING_RE`: número passa a `\d[\d.]*(?:-[A-Z])?` — captura a corrida
  numérica inteira **com** pontos de milhar e o sufixo de letra (`1.240-A`).
- Loader (`_format_article_line`): **preserva** o ponto no heading (`## Art. 1.000`) por fidelidade
  de citação; remove o ponto só para decidir o ordinal.
- Chunker:
  - `_id_article`: `replace(".", "")` → id sempre dotless e estável (`cc-10406-2002-art-1784`).
  - `_render_article`: normaliza para a forma jurídica canônica — ordinal 1–9 (`6º`), agrupamento
    de milhar para ≥1000 (`1784`/`1.784` → `1.784`, `1240-A` → `1.240-A`). Duas grafias da fonte
    (`1337` vs `1.337`) convergem para um único display e um único id.

Sem hard-code de faixa: qualquer artigo presente na fonte é capturado.

## 3. Alcance por código — esperado vs obtido (antes → depois)

| código | norm | esperado (máx) | máx ANTES | máx DEPOIS | distintos (base) | status |
|--------|------|---------------:|----------:|-----------:|-----------------:|--------|
| CC | 10406 | 2046 | **1337** | **2046** | 2037 | OK |
| CPC | 13105 | 1072 | **999** | **1072** | 1072 | OK |
| CP | 2848 | ~361 | 361 | 361 | 351 | OK |
| CPP | 3689 | 811 | 811 | 811 | 804 | OK |
| CLT | 5452 | ~922 | 922 | 922 | 907 | OK |
| CTN | 5172 | 218 | 218 | 218 | 202 | OK |
| CF/88 | 1988 | 250+ADCT | 250 | 250 | 250 | OK |

Apenas CC e CPC tinham defeito; os outros 5 já estavam corretos (nenhum usa separador de milhar).

**Distintos < máx = lacunas legítimas, não bug.** No CC há uma única lacuna contígua: arts.
**1.621–1.629** (adoção), **revogados** pela Lei 12.010/2009 e ausentes do texto compilado —
verifiquei que não constam da fonte (`NOT IN SOURCE`). As demais diferenças são artigos revogados
isolados + sufixos `-A/-B` que compartilham o número base. Família (1.511+) e Sucessões
(1.784–2.046) agora presentes (ex.: `Art. 1.511`, `Art. 1.784`, `Art. 2.046`). Regra #1 respeitada:
nada inventado, só o que está na fonte vendada.

## 4. Reingestão / idempotência

- `statutes_chunks.jsonl` regenerado: **6169 chunks**, **6169 chunk_ids únicos, 0 colisões**.
  (Total inalterado: o fix corrige os *tokens*, não o nº de seções no documento.)
- Desambiguação `-occ-K` mantida para reinícios estruturais (CF/88 corpo × ADCT etc.).
- Idempotência byte-estável: 2 execuções → sha256 idêntico
  `31a1fbf09f7dd016396a143cdab078e16c9ea2945297457f6b54a5e619ef1515`.
- `cdc_chunks.jsonl` intacto (130 chunks; CDC não usa milhar, `content_hash` inalterado).

## 5. Teste de regressão (lê fonte vendada, offline)

- `tests/unit/ingestion/test_code_article_coverage.py` (novo): para os 7 códigos, parametriza
  artigos-âncora de cauda que **devem** existir (CC 1.000/1.511/1.711/1.784/2.046; CPC 1.000/1.072;
  CP 359/361; CPP 800/811; CLT 900/922; CTN 217/218; CF 249/250) lendo o HTML vendado real via
  `CORE_CODES` → `html_to_markdown` → `chunk_document`. Mais `test_cc_reaches_full_range`
  (máx == 2046, >1900 artigos). Pin contra o buraco voltar silenciosamente.
- `tests/unit/ingestion/test_planalto_html_loader.py` (+1): `test_thousands_separator_articles_are_captured`
  — fixture sintética com `Art. 1.000`/`1.711`/`1337`/`2.046`; afirma display dotted, id dotless,
  e que nenhum vira `Art. 1`.

## 6. Lint / testes (resultado real)

- `ruff check packages/ingestion apps/worker/jobs tests/unit/ingestion` → **All checks passed!** (C90 ≤ 10).
- `mypy packages apps` → **Success: no issues found in 97 source files**.
- `pytest tests/unit/ingestion/` → **52 passed**.
- Suíte completa: em execução (notificação ao concluir); subconjunto do módulo verde.

## Arquivos tocados
- `packages/ingestion/loaders/planalto_html.py` — regex de artigo + preservação do milhar no heading.
- `packages/ingestion/chunker.py` — regex de heading + `_id_article`/`_render_article` (milhar).
- `tests/unit/ingestion/test_code_article_coverage.py` (novo).
- `tests/unit/ingestion/test_planalto_html_loader.py` (+1 teste).
- `data/generated/statutes_chunks.jsonl` regenerado (gitignored).
