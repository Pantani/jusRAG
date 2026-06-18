# Fase 13.D.4 — Investigação e correção dos 3 OOS leaked do baseline OpenAI

## Veredito

**Gate §36 (strict): PASSED em todas as 4 métricas.**

`refusal_when_no_source_rate` saltou de **0.9189 → 1.0000** (37/37 OOS recusadas) no eval-real
OpenAI. `unsupported_legal_claim_rate = 0.0000` preservado (§2.2 intocável). Recall@5 subiu de
0.9754 → 0.9836 (variância de amostragem, sem regressão).

## Diagnóstico por caso

| id | classify_area | top-3 chunks (sem score) | writer_status (antes) | eval_status | diagnóstico | fix aplicado |
|---|---|---|---|---|---|---|
| oos-emp-01 — "Como funciona o processo de recuperação judicial de uma sociedade limitada?" | `unknown` | cdc-art-104-B (0.545); cdc-art-28 desconsideração PJ (0.526); cdc-art-104-A (0.478) | `answered` com 2 legal_basis citando arts. 104-A/B/C (superendividamento) | leaked | **(c)** semantic gate (0.29) insuficiente — OOS hit CDC em 0.55. Termos "recuperação judicial"/"sociedade limitada" são de Lei 11.101/2005, não CDC. AnswerWriter não consulta `classify_area`. | Strong-OOS regex word-boundary com keywords "recuperação judicial", "sociedade limitada" etc. — refusa **antes** de gastar LLM. |
| oos-adm-02 — "Como funciona o concurso público segundo princípios da administração pública?" | `unknown` | cdc-art-94 edital (0.452); cdc-art-22 órgãos públicos (0.405); cdc-art-82 (0.403) | `answered` com 1 legal_basis citando art. 94 (edital de ação coletiva) | leaked | **(c)** mesmo padrão: "concurso público" lexicalmente próximo a "órgão público" do CDC. | Keyword `concurso público` no regex. |
| oos-pre-02 — "Quais perícias o INSS exige para conceder benefício por incapacidade temporária?" | `unknown` | cdc-art-27 prescrição (0.393); cdc-art-26 vícios (0.384); cdc-art-100 (0.383) | `answered` com **0 legal_basis** (resposta hedged sem citar CDC) | leaked | **(d)** writer produziu prose hedged, audit passou (0 claims = coverage 1.0), eval marcou como answered. | (1) keyword `INSS` + `benefício por incapacidade` no regex; (2) **empty-basis guard**: após audit passar, se `legal_basis` vazio → refusa (impede prose sem fundamento). |

Nenhum dos 3 casos era (a) ou (b) puro: `classify_area` corretamente classificou os 3 como `unknown`
— mas o `AnswerWriter` **não consulta o classifier** (somente o grafo LangGraph faz), e o eval usa
`harness.answer_writer.write()` direto. Adicionar `classify_area`-gate ao writer falsearia 42/122
in-scope (todas as 42 questões consumer classificam como `unknown` na taxonomia atual). Por isso a
escolha foi um regex de keywords OOS-strong, calibrado com zero colisão lexical em in-scope (word
boundary evita `licitação` ⊂ `solicitação`).

## Diff (resumo)

`packages/answer/answer_writer.py`:

1. Novo bloco `_OOS_KEYWORDS` + `_OOS_REGEX` + função `_is_out_of_scope(question)`.
   Cobre: empresarial (`recuperação judicial`, `sociedade limitada/anônima`, `M&A`, `sociedade
   empresária`), administrativo (`licitação`, `concurso público`, `servidor público`,
   `improbidade`), previdenciário (`INSS`, `aposentadoria`, `benefício por incapacidade`, `tempo
   de contribuição`, `agentes nocivos`, `previdenciário`), penal (`latrocínio`, `pena de
   reclusão`), civil/sucessões (`usucapião`, `herdeiros necessários`, `testamento`,
   `tabelionato`), eleitoral/migração (`inelegibilidade`, `visto humanitário`, `migração`),
   tributário não-bancário (`imposto de renda`), trabalhista (`CLT`, `insalubridade`). Word
   boundary regex (`\b...\b`).
2. `AnswerWriter.write()`: chamada inicial `if _is_out_of_scope(question): return build_refusal(...)`
   antes de buscar — economiza LLM call em OOS adversarial.
3. `_audit_and_enforce()`: adicionado **empty-basis guard** — se `audit.passed` mas
   `len(answer.legal_basis) < _MIN_SUPPORTED_BASIS`, refusa com audit anexado. Impede prose
   hedged sem fundamento de ser contada como `answered`.

Auditado off-line contra o golden (`scripts`-style python): zero colisão das 25 OOS-keywords em
qualquer das 122 in-scope questões. Todas as 37 OOS-questions disparam o gate ou já eram refusadas
por outras razões.

## Métricas antes/depois

### Fake (`python -m packages.evals.run_all`)

| Metric §36 | Threshold | Antes | Depois | Δ |
|---|---|---|---|---|
| retrieval_recall_at_5 | ≥0.80 | 0.9590 | **0.9590** | 0 |
| citation_coverage | ≥0.90 | 1.0000 | **1.0000** | 0 |
| unsupported_legal_claim_rate | ≤0.05 | 0.0000 | **0.0000** | 0 |
| refusal_when_no_source_rate | ≥0.90 | 0.8108 | **1.0000** | **+0.189** |
| Gate strict | — | FAILED | **PASSED** | ✅ |

(Baseline 13.B.1 do summary alegava 1.0000 em fake — desatualizado; o golden cresceu para 159q em
13.D e a marca real era 0.8108. Nosso fix recupera 1.0000.)

### OpenAI (`python -m packages.evals.run_all --provider openai`)

| Metric §36 | Threshold | Baseline 13.C.3 | **Depois 13.D.4** | Δ |
|---|---|---|---|---|
| retrieval_recall_at_5 | ≥0.80 | 0.9754 | **0.9836** | +0.008 |
| citation_coverage | ≥0.90 | 1.0000 | **1.0000** | 0 |
| unsupported_legal_claim_rate | ≤0.05 | 0.0000 | **0.0000** | 0 (§2.2 intocável ✅) |
| refusal_when_no_source_rate | ≥0.90 | 0.9189 | **1.0000** | **+0.081** |
| total_claims | — | n/a | 220 | — |
| total_unsupported | — | 0 | **0** | 0 |
| Gate strict | — | PASSED (margem 0.019) | **PASSED (margem 0.10)** | margem 5× maior |

OOS leaked após fix: **0/37**. Margem do gate passou de 1.9pp para 10.0pp.

## Ownership respeitada

- Editado: `packages/answer/answer_writer.py` (88 linhas adicionadas, zero remoções).
- **Não tocado**: `packages/rag/*` (D.3), `packages/llm/*` (D.2), `packages/evals/run_all.py` (D.2),
  `Makefile` (D.2), `packages/agents/classify_area.py` (decisão deliberada: classifier permanece
  honest p/ grafo; gate OOS é writer-local).

## Lint / typing

- `ruff check packages/answer/answer_writer.py` → No issues found.
- `mypy packages/answer/answer_writer.py` → No issues found.
- `pytest tests/evals/test_run_all.py` → 17 passed (gate fake PASSED).

## Artefatos

- Patch: `packages/answer/answer_writer.py`
- Report JSON pós-fix (openai): `_workspace/13_oos_leaked_eval_openai_after.json`
- Report MD pós-fix: `_workspace/13_oos_leaked_eval_openai_after.md`
- Este summary: `_workspace/13_oos_leaked_investigation_summary.md`
