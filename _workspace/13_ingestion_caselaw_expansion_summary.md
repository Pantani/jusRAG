# Tarefa 13.A.2 — Expansão STJ consumer jurisprudence seed

## Resultado

- `data/seed/case_law/stj_consumer_seed.jsonl`: **30 entradas** (5 originais + 25 novas).
- Breakdown: **15 súmulas** + **15 recursos repetitivos / Temas**.
- `make ingest-case-law` (`python -m apps.worker.jobs.ingest_case_law`) gera 30 chunks
  `doc_type=case_law` em `data/generated/case_law_chunks.jsonl`.

## Mudanças de código

Para suportar repetitivos sem alterar o schema (`CaseLawDocument`, propriedade do legal-domain):

1. `packages/ingestion/loaders/stj.py` — loader agora aceita duas formas de entrada:
   - Súmula: chave `summary_number` → `document_id = stj-sumula-N`, `case_number = "Súmula N"`.
   - Repetitivo: chave `theme_number` (+ `case_number` REsp paradigma) → `document_id = stj-tema-N`,
     `case_number` = REsp informado.
   - Campo opcional `verification_status` em qualquer entrada é encaminhado para `metadata`.
2. `packages/ingestion/chunker.py:chunk_case_law` agora propaga `doc.metadata` (não-`None`) para a
   `metadata` do `LegalChunk`, levando `summary_number` / `theme_number` / `verification_status`
   ao payload do indexador (§9 / §40.4).
3. `tests/unit/ingestion/test_stj_loader.py` — bound `4 ≤ len ≤ 6` substituído por `≥ 30` com
   asserções de mistura (`≥15 súmulas`, `≥15 repetitivos`) + novo teste
   `test_repetitivo_entry_loads_with_theme_metadata`.

## Verification status (§2 — NUNCA INVENTAR)

Honestidade explícita: a fonte oficial STJ não foi consultada via rede durante esta tarefa. Marquei
como `verification_status: "needs_review"` toda entrada cujo enunciado/Tema/REsp paradigma não pude
citar verbatim com alta confiança. **Bloquear release v1.2 até revisão humana** dos seguintes IDs
contra a fonte oficial (https://www.stj.jus.br/sumulasstj/, /repetitivos-temas/):

### Súmulas a revisar (10)

- `stj-sumula-321` (CDC × previdência privada aberta)
- `stj-sumula-359` (notificação prévia cadastro de proteção ao crédito)
- `stj-sumula-385` (anotação irregular SCPC)
- `stj-sumula-404` (dispensabilidade AR na notificação)
- `stj-sumula-472` (comissão de permanência)
- `stj-sumula-477` (decadência art. 26 CDC × prestação de contas bancária)
- `stj-sumula-532` (monitória sobre cheque prescrito)
- `stj-sumula-595` (responsabilidade IES por curso não reconhecido)
- `stj-sumula-608` (CDC × planos de saúde, salvo autogestão)
- `stj-sumula-632` (inversão do ônus da prova em seguro)

### Repetitivos a revisar (15) — todos os 15 Temas adicionados

- Temas 666, 717, 887, 932, 938, 939, 950, 952, 958, 960, 988, 990, 1006, 1020, 1030.
- Para cada um: confirmar (a) número exato do Tema, (b) REsp paradigma e número de processo,
  (c) wording exato da tese fixada, (d) datas de julgamento/publicação.
- Ementas atuais são *resumos topicais* mantidos curtos e consumer-específicos para não inventar.

### Verificadas (5) — entradas originais inalteradas

`stj-sumula-130`, `stj-sumula-297`, `stj-sumula-302`, `stj-sumula-479`, `stj-sumula-543`.

## Idempotência

```bash
$ python -m apps.worker.jobs.ingest_case_law && shasum data/generated/case_law_chunks.jsonl
f45a068008cdf0c56c30521d2dcad38787397a82  data/generated/case_law_chunks.jsonl
$ python -m apps.worker.jobs.ingest_case_law && shasum data/generated/case_law_chunks.jsonl
f45a068008cdf0c56c30521d2dcad38787397a82  data/generated/case_law_chunks.jsonl
```

Bytes idênticos em re-runs consecutivos. Dedupe por `content_hash` confirmado pelo teste
`test_idempotent_by_hash`.

## Testes & lint

- `pytest tests/unit -q` → **138 passed** (incluindo 4 novos / atualizados em
  `test_stj_loader.py`).
- `ruff check .` → clean (sem novos warnings).
- `mypy packages/ingestion apps/worker` → clean. (Erro pré-existente em
  `packages/rag/hybrid_retriever.py:149` não é desta tarefa; arquivo é de propriedade do retrieval.)

## Regressão de eval — escalada para `answer`/`evals` (não bloqueia esta entrega)

Após a expansão, `tests/evals/test_answer_eval.py::test_refusal_rate_meets_threshold_on_seed` e
dois testes correlatos em `test_run_all.py` falham:

```text
refusal_when_no_source_rate = 0.5714 (threshold 0.9)
failing_case_ids = ['oos-imposto-territorial', 'oos-crime-homicidio', 'oos-usucapiao-imovel']
```

**Causa-raiz:** `packages/answer/answer_writer.py:_MIN_SEMANTIC_SCORE = 0.20` foi calibrado contra
um corpus de 5 chunks. Com 30 chunks no índice, queries OOS encontram vizinhos casuais (súmula 595
e similares) acima de 0.20 (~0.30–0.36) via overlap léxico do `FakeEmbeddingProvider`
(bag-of-words). O conteúdo das súmulas adicionadas é legítimo e CDC-específico — nenhum invento.

**Pertinência:** `packages/answer/` é propriedade do agente `answer`; threshold de refusal e
estratégia de scope-gate ficam lá. `packages/evals/harness.py` é propriedade de `eval`.

**Recomendação de follow-up (não nesta PR):**
1. `answer` revisa `_MIN_SEMANTIC_SCORE` (sugestão: subir para ~0.40 ou tornar adaptativo por
   percentil), ou adiciona gate por `legal_area` quando a query não classifica como `consumer`.
2. Alternativamente, `eval` injeta `min_semantic_score` configurável em `build_harness` para
   recalibrar contra o corpus expandido sem regredir produção.

## Próximos passos sugeridos

1. Revisão humana das 25 entradas `needs_review` antes do tag v1.2 (cross-check com
   https://www.stj.jus.br/sumulasstj/ e https://www.stj.jus.br/repetitivos-temas/).
2. Ajuste de calibração no `answer` (acima).
3. Re-rodar `make eval` e atualizar baseline de quality gates (§36).
