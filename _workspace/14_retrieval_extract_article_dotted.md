# 14 — Retrieval: extract_article com separador de milhar (PR #3, CodeRabbit Critical)

## Bug
`extract_article` parava no primeiro dígito (`(\d+)`). Para `"art. 1.238"` retornava `"1"`,
quebrando o contrato documentado (formas dotted e dotless devem convergir para o mesmo token
dotless) e o boost de `exact_citation_match` para artigos altos de CC/CPC quando a query vem
com ponto. Follow-up sinalizado pelo ingestion após o fix do campo `article` no chunker.

## Regex antes/depois
Antes:
```python
_ARTICLE_RE = re.compile(r"\bart(?:igo|\.)?\s*(\d+)", re.IGNORECASE)
# extract_article: return match.group(1) if match else None
```
Depois:
```python
_ARTICLE_RE = re.compile(r"\bart(?:igo|\.)?\s*(\d[\d.]*[ºo°]?(?:-[A-Z])?)", re.IGNORECASE)
# extract_article: return match.group(1).replace(".", "") if match else None
```

Mudanças:
- Stem numérico `\d[\d.]*` captura dígitos internos com pontos de milhar (`1.238`).
- `.replace(".", "")` normaliza para o token **dotless** do campo `article` do chunker.
- Mantém o sufixo ordinal `[ºo°]?` e a letra `(?:-[A-Z])?` (ex.: `6º`, `1240-A`) — convergência
  total com `chunker._match_article` / `legal_ranker.exact_citation_match`.
- Ponto final de frase não é capturado: a classe `[\d.]*` só absorve dígitos/pontos contíguos ao
  número; `"art 12."` -> o regex captura `12` (o `.` final fica fora do grupo por não haver dígito
  após, e nada a remover).

## Casos validados (sanity real)
| query | resultado |
|-------|-----------|
| `art. 1.238` | `1238` (fix) |
| `art 1238` | `1238` (inalterado) |
| `art. 6º` | `6º` (sufixo ordinal preservado) |
| `art 12.` | `12` (não captura ponto final de frase) |
| `o que diz o art. 49 do CDC?` | `49` |
| `artigo 12` | `12` |
| `art 1240-A` | `1240-A` |
| `art. 1.240-A` | `1240-A` (milhar + sufixo) |
| `defeito do produto` | `None` |

## Asserção consequente atualizada
`tests/unit/ingestion/test_chunker.py::test_thousands_article_matches_ranker_citation_path`
(linha 172) — único arquivo tocado fora de `packages/rag/`, justificado: exercita
`packages.rag` e é consequência direta do fix.
```python
# antes (documentava o bug):
assert exact_citation_match(payload, extract_article("art. 1.238")) == 0.0
# depois:
assert exact_citation_match(payload, extract_article("art. 1.238")) == 1.0
```

## Lint/test real
- `pytest tests/unit/rag/ tests/unit/ingestion/test_chunker.py` -> **37 passed**
- `ruff check packages/rag/query_analyzer.py` -> All checks passed (C90 <= 10 ok)
- `mypy packages apps` (strict) -> Success: no issues found in 97 source files

## Arquivos
- `packages/rag/query_analyzer.py` (regex + normalização dotless)
- `tests/unit/ingestion/test_chunker.py` (asserção 0.0 -> 1.0)
