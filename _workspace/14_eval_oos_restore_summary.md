# 14 — Restauração do golden OOS após o sinal explícito determinístico (§36, §2.2)

## Mudança upstream consumida
`answer._is_out_of_scope` agora pré-recusa DETERMINISTICAMENTE (independe do embedding)
qualquer pergunta cujo texto case um regime corpusless via
`matched_out_of_scope_regime(question)` (agentic). Só UNKNOWN SEM match prossegue ao
retrieval. Consequência: itens que eu havia movido ao débito alegando vazamento sob fake
recusam agora determinístico (fake E denso) e devem VOLTAR ao golden OOS como `refused`.

## Tarefa 1 — verificação item→matched_out_of_scope_regime→destino
Rodado `matched_out_of_scope_regime(question)` em cada item do débito (e confirmado via
`answer._is_out_of_scope` que os True realmente pré-recusam):

| id | matched? | destino |
|----|----------|---------|
| oos-aposentadoria-inss | True | golden (restaurado) |
| oos-pre-01 | True | golden |
| oos-pre-02 | True | golden |
| oos-pre-03 | True | golden |
| oosx-prev-aposentadoria-tempo | True | golden |
| oosx-prev-incapacidade | True | golden |
| oos-emp-01 (recuperação judicial) | True | golden |
| oos-emp-02 (sociedade anônima) | True | golden |
| oosx-amb-licenciamento | True | golden |
| oosx-amb-eia-rima | True | golden |
| oosx-pi-marca-inpi | True | golden |
| oosx-pi-patente-prazo | True | golden |
| oosx-mar-transporte | True | golden |
| oos-declarar-bitcoin | False | débito (tax sub-tópico) |
| oos-tax-01..05 | False | débito (tax) |
| oos-imposto-territorial | False | débito (tax) |
| oos-ele-01 / oosx-ele-inelegibilidade | False | débito (eleitoral) |
| oos-int-01 / oosx-mig-visto-humanitario | False | débito (migração) |
| oos-fam-02 / oos-suc-02 / oos-suc-03 | False | débito (família/sucessões) |
| oos-emp-03 (M&A — sem termo de regime casado) | False | débito (empresarial) |
| oos-pen-02 (tese STF) | False | débito (penal-tese) |
| oosx-conc-cade | False | débito (concorrência) |
| oosx-aut-direitos-autorais | False | débito (autoral) |
| oosx-reg-civil-nascimento | False | débito (registro civil) |

13 restaurados ao golden; 19 permanecem em débito (grounding-dependentes reais).

Nota de fronteira: eleitoral, migração, internacional, família/sucessões, M&A, concorrência,
autoral e registro civil deram **False** — o vocabulário específico do enunciado NÃO casa
nenhum termo de `_OUT_OF_SCOPE_TERMS`. Logo dependem de grounding denso e ficam em débito.
Estender `_OUT_OF_SCOPE_TERMS` é pendência do agentic (não toquei código de answer/agentic).

## Tarefa 2 — recalibração dos testes (tests/evals/test_anti_overfit.py)
- Docstring reescrita: regimes que casam termo voltaram ao gate determinístico; débito guarda
  só o resíduo grounding-dependente.
- `_HELD_OUT_OOS_IDS` (antigo) dividido em dois conjuntos held-out:
  - `_HELD_OUT_DETERMINISTIC_OOS_IDS` (amb, pi, mar, prev) → novo teste
    `test_held_out_deterministic_oos_regimes_are_in_the_gate_golden` afirma presença no
    `out_of_scope_golden.yaml` (volta à cobertura held-out de "OOS recusa" via gate).
  - `_HELD_OUT_GROUNDING_DEBT_IDS` (conc, aut, reg-civil) → `test_held_out_grounding_debt_
    regimes_are_present_for_generalisation` afirma presença no débito.
- `test_debt_oos_set_spans_multiple_distinct_regimes` segue válido: variedade do débito = 13 (≥8).
- xfail revertido: NENHUM. O único xfail é `guarda-cc-1583`, MANTIDO — sua causa é a
  regressão real de síntese do answer (CC art. 1.583 recupera em top-5 mas a síntese puxa
  ruído de vizinhança e o auditor recusa), NÃO a pré-recusa removida. Permanece
  `xfail(strict)` e segue pendente no owner answer.

## Tarefa 3 — gate §36 (fake/offline strict) — números reais
`uv run python -m packages.evals.run_all` → Gate (strict): PASSED, exit 0.
Provider: embedding=fake, llm=fake. Golden: 207 (in-scope 188, out-of-scope 19).

- retrieval_recall_at_5    = 0.9415  (≥0.80) PASS
- citation_coverage        = 1.0000  (≥0.90) PASS
- unsupported_legal_claim_rate = 0.0000 (≤0.05) PASS
- refusal_when_no_source_rate  = 1.0000 (≥0.90) PASS  ← fecha honesto com os 13 regimes
  corpusless de volta recusando determinístico (sem band-aid de débito).

Por área (recall@5): civil 1.00 (18/18), constitutional 1.00 (10/10), consumer 0.9098
(111/122), criminal 1.00 (13/13), labor 1.00 (15/15), tax 1.00 (10/10) — todas PASS.

Gate de build: §36 falha o build quando `unsupported_legal_claim_rate` excede 0.05 (gate
strict ligado por padrão em `run_all`). Hoje 0.0000.

## Tarefa 4 — tamanho final por bucket
- OOS no golden (gate): 19 (6 administrative pré-existentes + 13 regimes restaurados).
- eval-real-debt: 19 (7 tax cohort A + 12 cohort B grounding-dependentes). Caiu de 32→19.
- in-scope no golden: 188.
- total golden: 207.

## Lint/test/gate reais
- `uv run pytest tests/evals/` → todos passam, 1 xfail (guarda-cc-1583), exit 0.
- `uv run pytest tests/evals/test_anti_overfit.py` → exit 0, 1 xfail.
- `uv run ruff check tests/evals/test_anti_overfit.py` → All checks passed.
- `uv run ruff check --select C901 tests/evals/` → All checks passed (CC<=10).
- `uv run mypy tests/evals/test_anti_overfit.py` → Success, no issues (strict).
- `uv run python -m packages.evals.run_all` → Gate (strict): PASSED.

Offline, fake providers determinísticos, sem rede. Ownership respeitado: alterado apenas
data/seed/questions/ (out_of_scope_golden.yaml, out_of_scope_eval_real_debt.yaml) e
tests/evals/test_anti_overfit.py. Nenhum código de answer/agentic tocado.

## Pendência ao orquestrador
- agentic: estender `_OUT_OF_SCOPE_TERMS` para eleitoral, migração, concorrência, autoral,
  sucessões substantivas — então cohort B pré-recusa determinístico e volta ao golden.
- answer: regressão de síntese guarda-cc-1583 (ruído de vizinhança → recusa do auditor).
