# Codex PR #3 — fixes em `packages/agents/classify_area.py`

Dois bugs reais de classificação corrigidos por princípio, com testes de regressão.
Offline/determinístico, sem overfit (vocabulário de domínio + fronteira, não enunciados do golden).

## BUG 1 — match out-of-scope por substring crua (falso-positivo)

Antes, o gate usava `term in normalized`. `"licitação"` casava DENTRO de `"solicitação"`, então
`"solicitação de reembolso ao fornecedor"` (consumo legítimo, com corpus) era rotulado
`administrative` e o §14 recusava antes do retrieval — recusava o que a base cobre.

### Técnica de boundary-match

Helper único `_matches(term, normalized)`:

```python
re.search(r"\b" + re.escape(term), normalized) is not None
```

- **Fronteira inicial obrigatória (`\b`)**: o caractere antes do termo não pode ser `\w`.
  Em `"solicitação"`, o `l` interno é precedido por `o` (`\w`) → `\blicitação` NÃO casa.
  Em `"licitação ..."`, o `l` é precedido por início/espaço → casa.
- **Borda final aberta (sem `\b` no fim)**: preserva os stems offline — `"tributár"` ainda casa
  `"tributária"/"tributário"`, `"empregad"` casa `"empregado"/"empregada"`. Um `\b` final
  quebraria isso (o stem termina no meio da palavra).
- **Frases multi-palavra** (`"servidor público"`, `"registro de marca"`, `"contrato de trabalho"`)
  ancoram no primeiro token e seguem casando como frase.
- Acentos: regex sobre `str` trata `á/é/ç` como `\w` (Unicode), então `\b` se comporta como
  esperado em torno de palavras acentuadas. `re.escape` é defensivo sobre vocabulário confiável.

Aplicado a `_score_area` (keywords por área) E a `_out_of_scope_match` (regimes sem corpus),
mantendo a precedência out-of-scope (regime sem corpus vence) já existente.

CC do helper trivial; `_score_area`/`_out_of_scope_match` permaneceram simples (ruff C90 ok).

## BUG 2 — `contrato` genérico (civil) roubava queries de LABOR

`"contrato de trabalho"`: civil=1 (`contrato`) e labor=1 (`trabalh`); `max` mantinha a primeira
chave do dict (CIVIL) no empate → grafo filtrava `legal_area=civil` e perdia os chunks da CLT.

### Solução do empate

Frase forte adicionada ao LABOR: `"contrato de trabalho": 2`. Agora:
- `"contrato de trabalho"` → labor 3 (frase 2 + `trabalh` 1) vs civil 1 → **LABOR**.
- `"rescisão do contrato de trabalho"` → labor 5 (`rescisão` 2 + frase 2 + `trabalh` 1) vs civil 1.
- Casos civis intactos: `"contrato de locação"` → civil 3 (`locação` 2 + `contrato` 1);
  `"contrato e obrigação de indenização por dano moral"` → civil (sem cues de labor).

Solução localizada na frase discriminante de domínio — não mexe no desempate genérico do `max`,
evitando regressão nos casos civis legítimos. Sem casar enunciados do golden.

## Casos de teste antes/depois

| Pergunta | Antes | Depois |
|---|---|---|
| `solicitação de reembolso ao fornecedor` | administrative (recusa) | **consumer** |
| `licitação para contratação de servidor` | administrative | administrative (mantido) |
| `contrato de trabalho` | civil (perde CLT) | **labor** |
| `rescisão do contrato de trabalho` | civil/labor instável | **labor** |
| `contrato de locação` | civil | civil (mantido) |
| `contrato e obrigação de indenização por dano moral` | civil | civil (mantido) |

Novos testes: `test_substring_oos_term_does_not_false_positive_on_longer_word`,
`test_contrato_de_trabalho_resolves_to_labor_not_civil`.

## Lint/test real

- `pytest tests/unit/agents/test_classify_area.py` → **34 passed** (0.12s)
- `pytest tests/unit/agents/` (suíte completa, graph + researchers) → **46 passed** (0.16s)
- `ruff check packages/agents/classify_area.py tests/...` → **All checks passed**
- `mypy packages/agents/classify_area.py` (strict) → **Success: no issues found**
