# Fase 14 — Fix: marcador ordinal dentro do sufixo de artigo (`Art. 1º-A`)

PR #3, CodeRabbit (Major) — `packages/ingestion/loaders/planalto_html.py`, `_ARTICLE_RE`.

## Bug

O regex casava o sufixo `-[A-Z]` **antes** do marcador ordinal. Para a forma canônica
brasileira de artigo emendado em arts. 1º–9º (`Art. 1º-A`), capturava só `1` e vazava
`-A` para o corpo do caput — id de artigo errado e texto legal corrompido.

## Regex — antes / depois

Antes:
```
^\s*Art\.?\s*(\d(?:[\d.]*\d)?(?:-[A-Z])?)(?:[º°]|(?-i:o))?\.?\s*(.*)
```
Depois (sugestão do CodeRabbit, validada — ordinal movido para DENTRO do grupo,
antes do sufixo):
```
^\s*Art\.?\s*(\d(?:[\d.]*\d)?(?:(?:[º°]|(?-i:o))?-[A-Z])?)(?:[º°]|(?-i:o))?\.?\s*(.*)
```

Cada segmento permanece opcional, então as variantes anteriores continuam válidas.
O `(?-i:o)` case-sensitive foi preservado — o "O" maiúsculo de início de caput não é
comido.

## Casos validados (regex + `_format_article_line`)

| Input | group(1) | article token | body |
|-------|----------|---------------|------|
| `Art. 1º-A. O texto segue.` | `1º-A` | `1º-A` | `O texto segue.` |
| `Art. 1-A. corpo.` | `1-A` | `1º-A` | `corpo.` |
| `Art. 10. O fornecedor.` | `10` | `10` | `O fornecedor.` |
| `Art. 1.238. milhar.` | `1.238` | `1.238` | `milhar.` |
| `Art. 5-A. corpo.` | `5-A` | `5º-A` | `corpo.` |
| `Art. 1o Esta lei.` | `1` | `1º` | `Esta lei.` |
| `Art. 12º Os direitos.` | `12` | `12` | `Os direitos.` |

Convenção coerente com `_match_article`: token de display com ordinal preservado/normalizado
(`1º-A`); `1º-A` (com ordinal na fonte) e `1-A` (sem) convergem para o mesmo token. O caput
"O..." é preservado em todos os casos.

## Teste adicionado

`tests/unit/ingestion/test_planalto_html_loader.py`:
- `test_ordinal_suffix_article_is_captured` — `Art. 1º-A. O texto...` gera heading
  `## Art. 1º-A`, preserva o caput `O texto do artigo emendado.`, e `-A` não vaza.
- `test_ordinal_suffix_article_chunks_correctly` — round-trip até o chunk: `article == "1º-A"`
  com caput intacto.

## ATENÇÃO — o seed MUDOU (ao contrário do que o CodeRabbit afirmou)

CodeRabbit disse que não havia instâncias em `data/seed`. **Falso.** O **CPP**
(`data/seed/criminal_cpp/_source/planalto_del3689compilado.html`) contém os artigos do
juiz das garantias (Lei 13.964/2019): `Art. 3º-A` até `Art. 3º-F`.

Antes do fix, esses 6 artigos eram corrompidos:
- 7 headings idênticos `## Art. 3º` (colisão de id `art-3`), com `-A. O`, `-B. O`, ...
  vazando para o corpo.

Depois do fix: `3º`, `3º-A`, `3º-B`, `3º-C`, `3º-D`, `3º-E`, `3º-F` — distintos e corretos.

Isto é **correção de corrupção real**, não regressão. Mas significa que o JSONL gerado para o
CPP muda ao reingerir.

### Impacto em disco

- `data/seed/cdc/cdc.md`: **byte-idêntico** (regen == committed). Confirmado.
- `data/generated/cdc_chunks.jsonl`: **hash inalterado**
  `6291d06cd438b3e7274cf470f6d2306ee0ecfe1345a3873cbb3d2c6419f11f61` — nenhuma regeneração do
  artefato CDC commitado.
- Demais 6 códigos federais (CC, CPC, CF, CP, **CPP**, CLT, CTN) **não têm `.md` commitado** —
  são gerados on-the-fly no ingest. Só o **CPP** muda (correção dos arts. 3º-A–3º-F); os outros
  5 markdowns são byte-idênticos antes/depois (diff de hashes vazio).

Nenhum arquivo de seed versionado mudou em disco. A mudança no CPP só aparece ao regenerar seu
JSONL — e é uma melhoria (descorrupção). Decisão de regenerar fica com você.

## Lint / test (reais)

- `pytest tests/unit/ingestion/` — 51 passed.
- `ruff check` (loader + teste) — All checks passed.
- `ruff check --select C901` — passed (CC ≤ 10).
- `mypy` (strict, loader) — Success, no issues.
- Offline: nenhum acesso de rede.
