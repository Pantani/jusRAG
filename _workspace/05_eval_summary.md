# Fase 5 — Avaliação de citação + eval de alucinação (v0.5) — eval-agent

Data: 2026-06-17. Agente: eval. Skill: legal-evals. Fonte: §12.8, §12.11, §21, §36.

## Arquivos criados (ownership eval-agent)

- `packages/evals/__init__.py` — docstring da suíte (Fase 5 entrega lado citação/alucinação).
- `packages/evals/citation_eval.py` — eval de citação que REUSA `audit_claims` da answer.
- `tests/evals/__init__.py` — pacote de testes de eval.
- `tests/evals/test_unsupported_claims.py` — eval de alucinação simulada (§12.8) + gate.

NÃO toquei: `packages/answer`, `packages/legal_types`, `packages/rag`, `packages/ingestion`,
`apps/`, `Makefile`, `pyproject.toml`. Sem rede.

## O que `citation_eval` expõe para o `run_all` da Fase 8

Funções/dataclasses puras, determinísticas, offline:

- `AnswerCase{case_id, short_answer, legal_basis: tuple[LegalClaim], chunks: tuple[AuditChunk]}`
  — entrada por pergunta golden; espelha exatamente os inputs do auditor (reuso direto).
- `audit_case(case) -> CaseAudit` — score por caso via `audit_claims` (NÃO reimplementa lógica).
- `evaluate_citations(cases, *, max_unsupported_rate=0.05, min_coverage=0.90) -> CitationEvalReport`
  — agrega o corpus. `unsupported_legal_claim_rate` é **micro-averaged** (total unsupported /
  total claims), não média de taxas, para que uma resposta muito alucinada não seja diluída.
- `CitationEvalReport` com `citation_coverage`, `unsupported_legal_claim_rate`, `total_claims`,
  `total_unsupported`, `cases: list[CaseAudit]`, `coverage_passed`, `unsupported_passed`,
  `passed` (property = ambos gates), `failing_case_ids`, e `.as_dict()` no formato
  `{metric: {value, threshold, passed}, ..., failing_case_ids, cases}` — pronto para o JSON/MD
  do `run_all`.

Contagem de claims por caso usa `extract_claims` do auditor (mesma extração, sem divergência).

## Prova do gate de threshold (§36)

`evaluate_citations` aplica os dois gates v1:
`unsupported_legal_claim_rate <= 0.05` (gate de build de "não alucinar") e
`citation_coverage >= 0.90` (reportado). Coberto por `tests/evals/test_unsupported_claims.py`:

- `test_hallucinated_claim_is_detected_per_case` — claim citando `art. 999` (fora do contexto
  recuperado, só arts. 12/49 no seed) é flagado; aparece em `unsupported_claims`, caso `passed=False`.
- `test_unsupported_rate_is_micro_averaged` — 3 grounded + 1 hallucinado ⇒ 2/8 = 0.25 (cada caso
  rende 2 claims: sentença do short_answer + legal_basis); coverage 0.75.
- `test_gate_fails_when_rate_exceeds_threshold` — rate 0.5 > 0.05 ⇒ `passed=False`,
  `unsupported_passed=False`, `coverage_passed=False`, `failing_case_ids=["h1"]`.
- `test_gate_passes_when_rate_within_threshold` — 20 grounded, rate 0.0, coverage 1.0 ⇒ `passed=True`.
- `test_gate_boundary_exactly_at_threshold_passes` — 1 unsupported em 20 ⇒ rate == 0.05 exato; o
  `<=` mantém o gate aprovado na fronteira (coverage 0.95 ≥ 0.90).
- `test_empty_corpus_is_vacuously_clean` — corpus vazio: coverage 1.0, rate 0.0, `passed=True`.
- `test_report_as_dict_carries_thresholds_and_failures` — `.as_dict()` carrega valor/threshold/pass
  por métrica e `failing_case_ids` para depuração dirigida (consumo pelo relatório da Fase 8).

Limiar NÃO relaxado: `MAX_UNSUPPORTED_LEGAL_CLAIM_RATE=0.05`, `MIN_CITATION_COVERAGE=0.90` (§36).

## Gate de build — quando ligar

O gate de `unsupported_legal_claim_rate` é materializado em `CitationEvalReport.unsupported_passed`/
`passed`. No CI v1 ele deve ser ligado pelo `run_all` da Fase 8 (que falha o build em
`make eval`) **após o dataset golden de 30 perguntas estabilizar** — antes disso fica reportado
sem falhar build, para evitar flakiness durante desenvolvimento (orientação da skill legal-evals).
O dataset golden completo e `run_all` são ownership da Fase 8 (não criados aqui, conforme escopo).

## Saída de test/lint (capturada, real)

- `pytest tests/evals/ -v`: **7 passed**.
- `make test`: **112 passed**, 1 warning (StarletteDeprecation benigno) — 105 anteriores + 7 novos.
- `make lint`: `ruff check .` All checks passed; `mypy` Success: no issues in 66 source files.
- `ruff --select C901` em citation_eval.py + test: No issues found (CC ≤ 10).

## Pendências para donos de módulo

Nenhuma métrica abaixo de threshold no escopo entregue (eval estrutural com fakes determinísticos).
Quando o `run_all` da Fase 8 rodar sobre o golden real, qualquer `failing_case_ids` deve virar
tarefa para `answer` (claim sem suporte) ou `retrieval` (fonte esperada ausente) — não maquiar.
