# Phase 13.D.2 — `--sample-llm` + configurable Ollama timeout

## Motivação

Local LLM full eval em CPU (Ollama / llama3.1:8b) leva ~40h sobre as 159 golden questions.
`--sample-llm N` permite rodar retrieval em **todas** as 159q (rápido/barato) mas só `N` LLM
calls (amostra estratificada in-scope + OOS), validando o plumbing fim-a-fim e os gates §2.2
sem pagar o full run.

Caso de uso documentado:

```bash
# 10 questões (5 in-scope + 5 OOS), ~25min em CPU vs ~40h full.
EVAL_PROVIDER=local EVAL_SAMPLE_LLM=10 make eval-real
```

## Decisões de design

- **Estratificação deterministic, sem random.** `stratified_llm_sample(qs, N)`
  pega os primeiros `N//2` in-scope + primeiros `N//2` OOS preservando a ordem do
  YAML golden. Reprodutível por construção; o operador conhece exatamente os IDs
  rodados (registrados em `eval_report.json` como `llm_sampled.sampled_ids`).
- **`N` ímpar → slot extra vai para in-scope** (família maior — 122 in-scope vs
  37 OOS). Quando uma estratificação fica curta (ex.: N>74 e só temos 37 OOS),
  o resto é emprestado da outra estratificação para honrar `size`.
- **Retrieval continua full-set.** Só `produce_answers` (que dispara o LLM) e os
  evals derivados (citation, answer/refusal) operam no subset. Métricas
  `retrieval_recall_at_5` / `retrieval_precision_at_5` continuam estatisticamente
  válidas (full 122q in-scope).
- **Gates §36 viram informacionais sob amostragem.** Subset estatisticamente
  fraco; bloquear CI em N=4 seria ruído. `EvalSuiteResult.gate_passed()` retorna
  True quando `llm_sample.active`, e o report Markdown carimba "(amostra)" nas
  linhas LLM-bound + verdict "INFORMATIONAL". Modo full (default `--sample-llm 0`)
  mantém os gates strict bloqueantes intactos.
- **Ollama timeout via env, parse explícito.** `OLLAMA_TIMEOUT_SECONDS` lido no
  `__init__` do `OllamaLLMProvider`; argumento explícito vence. Valor inválido
  (não-float ou ≤0) levanta `RuntimeError` com mensagem clara — sem fallback
  silencioso (system rules §2/§6). Default 300s preservado.

## Diffs resumidos

- `packages/llm/ollama_provider.py`: `_resolve_timeout(explicit)` lê
  `OLLAMA_TIMEOUT_SECONDS`; constructor aceita `timeout: float | None`;
  expõe `provider.timeout` para inspeção.
- `packages/evals/run_all.py`:
  - novo `LLMSampleInfo` (size + sampled_ids + active);
  - `stratified_llm_sample(questions, size)` deterministic;
  - `run_suite(..., sample_llm=N)` — retrieval full, LLM subset;
  - `EvalSuiteResult.gate_passed()` retorna True sob sampling (informacional);
  - flag CLI `--sample-llm N` (default 0); `_print_summary` carimba "(amostra)".
- `packages/evals/report.py`: nova seção `## LLM sample (informational)` com
  size + IDs; gate verdict vira `INFORMATIONAL (amostra)`; linhas LLM-bound
  ganham sufixo "(amostra)".
- `Makefile`: `eval-real` aceita `EVAL_SAMPLE_LLM=N` (default 0).
- Tests novos:
  - `tests/evals/test_run_all.py`:
    - `test_sample_llm_runs_retrieval_full_but_llm_subset` (spy em
      `produce_answers` confirma `len(subset)==4`, retrieval recebe 159);
    - `test_stratified_llm_sample_is_deterministic_and_balanced` (2 in-scope + 2 OOS, ordem estável);
    - `test_sample_llm_report_marks_gate_informational` (gate informational + Markdown).
  - `tests/unit/llm/test_ollama_provider.py`:
    - `test_timeout_env_propagates` (`OLLAMA_TIMEOUT_SECONDS=60` → `provider.timeout==60.0`);
    - `test_timeout_env_default_when_unset` (300.0);
    - `test_timeout_env_explicit_arg_wins`;
    - `test_timeout_env_invalid_raises` (`abc` → `RuntimeError`);
    - `test_timeout_env_non_positive_raises` (`0`).

## Resultados

- `make lint` ✅ (ruff + mypy clean — 94 arquivos).
- `make test` → **198 passed, 4 failed**; as 4 falhas são **pré-existentes**
  (refusal rate=0.8649 < 0.90 com fake provider, problema do corpus 13.C
  rastreado em outras tarefas; **não introduzidas por 13.D.2**). Validado por
  `git stash` antes das edições — mesmas falhas.
- Novos testes de 13.D.2 (8 no total: 3 em `test_run_all.py` + 5 em
  `test_ollama_provider.py`) **todos verdes**.

## Não-objetivos

- Não toquei `refusal_when_no_source_rate` (fora de escopo; falha pré-existente
  é responsabilidade do answer/refusal owner).
- Não adicionei `OLLAMA_TIMEOUT_SECONDS` em `settings.py` — env-only é mais
  cirúrgico para um knob ops; promover a `Settings` se virar parte do contrato
  de configuração documentado.

## Commit

`feat(eval): sample-llm flag + configurable ollama timeout`
