---
name: legal-evals
description: >-
  Avaliação de qualidade do jus-rag-brasil — dataset golden de perguntas, métricas de retrieval
  (recall@k, precision@k), de citação (citation_coverage, citation_accuracy, unsupported_legal_claim_rate)
  e de resposta (refusal_when_no_source_rate, faithfulness), thresholds de aceite v1, e geração de
  relatório JSON/Markdown. Use ao implementar golden_questions, retrieval_eval, citation_eval,
  answer_eval, run_all, ou ao definir gates de qualidade que podem falhar o build. A fonte normativa é
  o Prompt Master §35-37.
---

# Avaliação de qualidade — jus-rag-brasil

Sem evals, "reduzir alucinação" é alegação não verificável. As evals transformam as regras de segurança
em métricas que podem **falhar o build** — é o que dá credibilidade ao projeto como produto técnico.

## Dataset golden — §35

`data/seed/questions/consumer_golden.yaml`, ≥30 perguntas de direito do consumidor na v1. Cada item:

```yaml
- id: consumer_001
  question: "O fornecedor responde objetivamente por defeito do produto?"
  expected_sources: ["Lei 8.078/1990 art. 12"]
  expected_terms: ["responsabilidade objetiva", "defeito do produto", "nexo causal"]
  forbidden_terms: ["responsabilidade subjetiva como regra"]
```

`expected_sources` valida retrieval/citação; `expected_terms` valida cobertura semântica da resposta;
`forbidden_terms` captura erros jurídicos específicos. Inclua perguntas **fora do escopo** para medir
recusa segura.

## Métricas — §36

| Métrica | Threshold v1 | O que mede |
|---------|--------------|------------|
| `retrieval_recall_at_5` | ≥ 0.80 | fontes esperadas aparecem no top-5 |
| `retrieval_precision_at_5` | (reportar) | proporção relevante no top-5 |
| `citation_coverage` | ≥ 0.90 | claims com fonte / claims totais |
| `citation_accuracy` | (reportar) | citação aponta ao chunk correto |
| `unsupported_legal_claim_rate` | ≤ 0.05 | claims sem suporte / claims totais |
| `refusal_when_no_source_rate` | ≥ 0.90 | recusa correta em perguntas fora do escopo |
| `answer_relevancy`, `faithfulness` | opcional | qualidade da resposta |

## Estrutura dos evals — §5

`packages/evals/`: `golden_questions.yaml` (ou lê o YAML do seed), `retrieval_eval.py`,
`citation_eval.py`, `answer_eval.py`, `run_all.py`. `make eval` → `python -m packages.evals.run_all`.

## Relatório

`run_all.py` gera `data/generated/eval_report.json` e `data/generated/eval_report.md`. O JSON é o
artefato máquina (CI consome); o MD é legível para humano. Inclua por métrica: valor, threshold,
pass/fail, e a lista de ids que falharam (para depuração dirigida).

## Gate de build — §36

`make eval` **pode falhar** quando `unsupported_legal_claim_rate` excede o threshold. Esse é o gate
que materializa "não alucinar" como regra executável. No CI v1, ligar o gate após o dataset estabilizar
para evitar flakiness durante o desenvolvimento — documente quando estiver ligado.

**Por que gate em unsupported-claim e não só em recall:** recall mede se achamos a fonte; o gate de
alucinação mede se afirmamos além dela. O segundo é o risco jurídico real e o que justifica o projeto.

## Evals sem rede

Evals de retrieval/citação usam dados seed e fake providers determinísticos (regra §13). Evals que
exigem LLM real (faithfulness com juiz LLM) ficam opcionais e fora do caminho de CI padrão, ou usam
respostas fixas gravadas. Não acoplar o gate de build a chamadas externas.

## Casos obrigatórios

- Retrieval recall nas perguntas seed (art. 12 para defeito, art. 49 para arrependimento, art. 6º para
  direitos básicos).
- Citation coverage em resposta bem fundamentada.
- Detecção de claim sem suporte em resposta alucinada simulada.
- Recusa segura em pergunta sem fonte na base seed.
