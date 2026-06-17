# Avaliação

A suíte de evals mede, de forma **reproduzível e offline**, a qualidade do retrieval e das respostas — em especial a fidelidade às fontes e a ausência de claims sem suporte. Está implementada em `packages/evals/` e roda via `make eval` (`python -m packages.evals.run_all`).

## Quality gates (v1, §36)

| Métrica | Threshold | Enforçado |
|---|---|---|
| `retrieval_recall_at_5` | ≥ 0.80 | por padrão (relaxável) |
| `citation_coverage` | ≥ 0.90 | por padrão (relaxável) |
| `unsupported_legal_claim_rate` | ≤ 0.05 | **sempre** |
| `refusal_when_no_source_rate` | ≥ 0.90 (perguntas fora do escopo) | por padrão (relaxável) |

O gate da `unsupported_legal_claim_rate` é a regra não-negociável de "não alucinar" (§2.1) e é **sempre** aplicado: violação resulta em código de saída não-zero, podendo **falhar o build**. Os demais gates são aplicados por padrão; definir `EVAL_GATE_STRICT=0` mantém apenas o gate de alucinação (útil enquanto um módulo dependente está sendo corrigido). O relatório registra pass/fail de **todos** os gates independentemente do modo.

O job também falha se o golden set tiver menos de **30** perguntas.

## Golden dataset

`data/seed/questions/consumer_golden.yaml` — **31 perguntas** de Direito do Consumidor (acima do mínimo de 30 da v1), incluindo perguntas dentro do escopo (com fonte esperada) e fora do escopo (que devem gerar recusa segura).

## Execução e relatório

```bash
make eval    # python -m packages.evals.run_all
```

`run_suite` carrega o golden, roda as três famílias de eval em uma única passada (`evaluate_retrieval`, `produce_answers` + `evaluate_answers`, `evaluate_citations`), agrega as métricas §36 e o veredito do gate, e escreve:

- `data/generated/eval_report.json`
- `data/generated/eval_report.md`

Um resumo é impresso no terminal com PASS/FAIL por métrica e o veredito final do gate.

Os evals **não acessam rede externa** — usam fake providers determinísticos para embeddings e LLM, garantindo reprodutibilidade no CI.

## Métricas

Reportadas pelo relatório:

- Retrieval: `retrieval_recall_at_5` (e métricas auxiliares de precisão).
- Citação: `citation_coverage`, `unsupported_legal_claim_rate`.
- Resposta: `refusal_when_no_source_rate`.

## Honestidade sobre os números

Os valores são medidos sobre um **seed pequeno** (6 artigos do CDC + 5 súmulas do STJ) e com **fake providers determinísticos**, não com o provider real OpenAI. Servem para validar a *arquitetura* — recall, cobertura de citação, recusa segura e ausência de claims sem suporte — de forma reproduzível em CI. **Não** são uma medida de desempenho do sistema em produção sobre todo o Direito do Consumidor.

## Componentes

- `packages/evals/golden.py` — carga e estatísticas do golden dataset.
- `packages/evals/harness.py` — harness offline (fake providers).
- `packages/evals/retrieval_eval.py`, `citation_eval.py`, `answer_eval.py` — as três famílias.
- `packages/evals/report.py` — render Markdown do relatório.
- `packages/evals/run_all.py` — orquestrador + gate de build (entry point de `make eval`).
