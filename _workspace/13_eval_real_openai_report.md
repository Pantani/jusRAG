# JusRAG Brasil — Eval Report

## Providers

- Embedding: **openai**
- LLM: **openai**

## Golden dataset

- Total: **159** (in-scope 122, out-of-scope 37)
- Minimum required (v1): 30 — meets minimum: **yes**

## Build gate (§36)

- Mode: **strict (all §36 thresholds)**
- Verdict: **PASSED**

## Metrics (§36 thresholds)

| Metric | Value | Threshold | Result |
| --- | --- | --- | --- |
| retrieval_recall_at_5 | 0.9754 | 0.8 | PASS |
| citation_coverage | 1.0000 | 0.9 | PASS |
| unsupported_legal_claim_rate | 0.0000 | 0.05 | PASS |
| refusal_when_no_source_rate | 0.9189 | 0.9 | PASS |
| answer_relevancy (heuristic) | 0.9836 | — | — |
| faithfulness (heuristic) | 0.8689 | — | — |

## Failing cases

- **Retrieval**: cdc-pre-02, cdc-ab-04, cdc-ab-08
- **Answer / refusal**: oos-emp-01, oos-adm-02, oos-pre-02

