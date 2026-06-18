# Avaliação

A suíte de evals mede, de forma **reproduzível e offline**, a qualidade do retrieval e das respostas — em especial a fidelidade às fontes e a ausência de claims sem suporte. Está implementada em `packages/evals/` e roda via `make eval` (`python -m packages.evals.run_all`).

## `make eval` vs `make eval-real`

| Target | Providers | Rede | Determinístico | Uso |
|---|---|---|---|---|
| `make eval` | **fake** (embeddings BoW + LLM determinístico) | nenhuma | sim | CI, regressão local, validação de arquitetura |
| `make eval-real` | **opt-in**: `openai` (embeddings + LLM) ou `local` (sentence-transformers + Ollama) | sim | não | medição manual de qualidade com providers reais, **não rodado em CI** |

`make eval-real` (Fase 13.B.2) faz **pré-flight**:

- Confere `OPENAI_API_KEY` quando `EVAL_PROVIDER=openai`.
- Confere Ollama acessível quando o LLM provider é `ollama`.
- Confere se a collection Qdrant `legal_chunks` tem **dim compatível** com o embedding selecionado (256 fake / 768 local / 1536 openai). Mismatch aborta com instrução explícita para recriar a collection — nenhum DELETE automático.

Invocações:

```bash
make eval                                                     # baseline CI
EVAL_PROVIDER=openai OPENAI_API_KEY=sk-... make eval-real      # OpenAI ponta a ponta
EVAL_PROVIDER=local make eval-real                             # sentence-transformers + Ollama
python -m packages.evals.run_all --provider=local --llm-provider=fake   # isolar retrieval real
```

O relatório (`data/generated/eval_report.{json,md}`) ganha campo `provider: {embedding, llm}` para registrar a configuração usada na medição.

## Quality gates (v1, §36)

| Métrica | Threshold | Enforçado |
|---|---|---|
| `retrieval_recall_at_5` | ≥ 0.80 | por padrão (relaxável) |
| `citation_coverage` | ≥ 0.90 | por padrão (relaxável) |
| `unsupported_legal_claim_rate` | ≤ 0.05 | **sempre** |
| `refusal_when_no_source_rate` | ≥ 0.90 (perguntas fora do escopo) | por padrão (relaxável) |

O gate da `unsupported_legal_claim_rate` é a regra não-negociável de "não alucinar" (§2.1) e é **sempre** aplicado: violação resulta em código de saída não-zero, podendo **falhar o build**. Os demais gates são aplicados por padrão; definir `EVAL_GATE_STRICT=0` mantém apenas o gate de alucinação (útil enquanto um módulo dependente está sendo corrigido).

O job também falha se o golden set tiver menos de **30** perguntas.

## Golden dataset

`data/seed/questions/consumer_golden.yaml` — **158 perguntas** (v1.2, ampliado de 31):

- **121 in-scope** — cobertura do CDC integral (princípios, vícios, decadência/prescrição, oferta, práticas abusivas, cobrança, bancos de dados, contratos, defesa em juízo, superendividamento), súmulas STJ (15) e Temas repetitivos (14). Inclui edge-cases: phrasing leigo, número de artigo explícito, ambíguas (2+ artigos plausíveis), pedido de aconselhamento explícito.
- **37 out-of-scope** — tributário, penal, trabalho, família, sucessões, empresarial, administrativo, previdenciário, eleitoral, internacional, civil-reais. Todas devem disparar **recusa segura**.

Cada candidato passou por probe determinística antes da inclusão: in-scope precisa ter o `expected_chunk_id` no top-5; out-of-scope precisa retornar `status=REFUSED`.

## Métricas atuais (fake providers, golden 158)

```
Provider: embedding=fake, llm=fake
Golden questions: 158 (in-scope 121, out-of-scope 37)
  [PASS] retrieval_recall_at_5       = 0.9669  (threshold 0.80)
  [PASS] citation_coverage           = 1.0000  (threshold 0.90)
  [PASS] unsupported_legal_claim_rate = 0.0000  (threshold 0.05)
  [PASS] refusal_when_no_source_rate = 1.0000  (threshold 0.90)
Gate (strict): PASSED
```

`precision_at_5` é reportado (`~0.17`, baixo por construção — gold é 1 chunk, top-5 retorna 5) mas **não gateado**.

## Como interpretar regressões

Quando um gate falha, **primeiro investigar a causa-raiz no produtor da métrica**, não recalibrar o threshold cegamente:

| Sintoma | Causa típica | Quem corrige |
|---|---|---|
| `retrieval_recall_at_5` cai | Corpus cresceu e o scoring vetorial perdeu separação (caso A.5 — TF L2 vs IDF); query nova com vocabulário fora do índice; chunk corrompido. | retrieval-agent (embedding/ranker/BM25 hybrid), não o gate |
| `citation_coverage` cai | `AnswerWriter` não anexou source para claim; `CitationAuditor` não casou termos. | answer-agent (writer/auditor) |
| `unsupported_legal_claim_rate` sobe | Claims sem chunk de suporte; threshold `_MIN_OVERLAP` do auditor frouxo para o corpus. | **NUNCA** relaxar o gate §2.1; corrigir auditor ou writer |
| `refusal_when_no_source_rate` cai | `_MIN_SEMANTIC_SCORE` do writer frouxo; OOS gold com vocabulário sobreposto ao corpus (falso-positivo léxico). | answer-agent (recalibrar threshold) ou eval (reescrever OOS) |

**Quando recalibrar thresholds (vs corrigir código):** apenas se houver evidência **quantitativa** de que a fronteira atual está mal-posicionada para o corpus efetivo. O patch da Fase 13.A.4 fez isso para `_MIN_OVERLAP` (0.18 → 0.40) e `_MIN_SEMANTIC_SCORE` (0.20 → 0.30) com grid F1 e separação medida entre supported/unsupported sobre o corpus de 160 chunks. A Fase 13.A.5 ajustou `_MIN_SEMANTIC_SCORE` para 0.29 após habilitar IDF dampening no fake provider. **Nunca** recalibrar para mascarar bug de retriever/writer.

## Componentes

- `packages/evals/golden.py` — carga e estatísticas do golden dataset.
- `packages/evals/harness.py` — `build_harness()` (fake) e `build_real_harness()` (providers reais).
- `packages/evals/retrieval_eval.py`, `citation_eval.py`, `answer_eval.py` — as três famílias.
- `packages/evals/report.py` — render Markdown do relatório (inclui seção `## Providers`).
- `packages/evals/run_all.py` — orquestrador + gate de build, argparse `--provider`/`--llm-provider`, pré-flight Qdrant.
