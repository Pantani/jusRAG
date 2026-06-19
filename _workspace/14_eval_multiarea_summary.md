# Fase E — Evals multi-área (golden por área + gates §36)

Dono: eval (`packages/evals/`, `data/seed/questions/`). Mede saídas de retrieval e answer
sobre o corpus multi-área (6329 chunks). Offline/determinístico (fake providers, sem rede).

## 1. Organização dos arquivos golden — decisão: um arquivo por área

`data/seed/questions/` agora contém:

| arquivo | área | nº perguntas |
|---------|------|-------------:|
| `consumer_golden.yaml` | consumer (+ OOS herdados) | 122 in-scope + OOS |
| `civil_golden.yaml` | civil (CC + CPC) | 10 |
| `criminal_golden.yaml` | criminal (CP + CPP) | 10 |
| `labor_golden.yaml` | labor (CLT) | 10 |
| `tax_golden.yaml` | tax (CTN) | 10 |
| `constitutional_golden.yaml` | constitutional (CF/88) | 10 |
| `out_of_scope_golden.yaml` | OOS (sem corpus) | 7 |

**Por que um arquivo por área e não um multiarea único:** ownership/diff limpos por área,
extensão incremental sem mexer no consumer, e `area` derivável do nome do arquivo. O loader
foi adaptado para consumir o padrão (ver §3).

Total carregado: **216 perguntas** (176 in-scope, 40 out-of-scope).
Distribuição in-scope por área (métrica): consumer 122, labor 13, criminal 11, civil 10,
constitutional 10, tax 10. (labor/criminal têm +3/+1 devido a reclassificações, §4.)

≥50 novas perguntas in-scope: **50** (5 áreas × 10), todas ancoradas em artigos REAIS do
corpus ingerido. Cada `expected_chunk_id` foi verificado contra `statutes_chunks.jsonl` e
validado em retrieval top-5 no harness offline (sem invenção — regra #1; o teste
`test_expected_chunk_ids_are_in_corpus` impede drift).

### Artigos ancorados (todos reais, verificados)
- civil: CC 186, 187, 927, 389, 421, 422, 206; CPC 300, 319, 373.
- criminal: CP 121, 155, 157, 171, 14, 26, 1º, 44; CPP 5º, 312.
- labor: CLT 3º, 442, 58, 71, 477, 483, 818, 4º, 457, 130.
- tax: CTN 3º, 113, 142, 150, 156, 9º, 124, 105, 121, 126.
- constitutional: CF 1º, 2º, 3º, 5º (×2), 6º, 7º, 37, 127, 145.

## 2. OOS honesto

`out_of_scope_golden.yaml` adiciona 7 perguntas de áreas **sem corpus** (Lei de Licitações
14.133, servidor 8.112, improbidade 8.429, INSS/previdenciário, eleitoral LC 64, migração
13.445), incluindo casos adversariais que compartilham tokens com áreas in-scope (CF art. 37
"administração pública") para confirmar recusa por grounding insuficiente, não por ausência de
overlap. Todos `expected_behavior: refused`, sem `expected_chunk_ids`.

## 3. Mudanças no carregador / evals (`packages/evals/`)

- `golden.py`: `load_golden()` sem argumento agora carrega e concatena **todos** os
  `*_golden.yaml` de `data/seed/questions/` (ordenados, determinístico); `load_golden(path)`
  ainda carrega um único arquivo (usado por testes). Novo campo `GoldenQuestion.area`
  (explícito via chave `area:` ou inferido do nome `<area>_golden.yaml`) e propriedade
  `metric_area` (refused agrupa em `out_of_scope`). `GoldenStats.per_area` adicionado.
- `retrieval_eval.py`: `RetrievalCase.area`; `AreaRecall` + `_per_area_recall`; recall@5
  micro-averaged **por área** além do agregado.
- `citation_eval.py`: `AnswerCase.area`/`CaseAudit.area`; `_per_area_citation` (coverage +
  unsupported rate por área).
- `answer_eval.py`: `answer_relevancy` por área (`_relevancy_per_area`); propaga `area` para
  os `AnswerCase`.
- `run_all.py`: expõe `golden.per_area` no JSON; imprime breakdown de recall por área.
- `report.py`: nova seção "Per-area metrics" (recall@5, coverage, unsupported, relevancy).
- O golden consumer **não foi alterado em estrutura** (sem chave `area:` → herda "consumer"
  do nome do arquivo); ids preservados.

## 4. Reclassificações (não é maquiagem — alinha o golden ao escopo atual)

A decisão do usuário tornou civil/criminal/labor/tax/constitutional **in-scope**. Vários OOS
do consumer_golden eram OOS *apenas* sob o corpus só-CDC. Sob o corpus multi-área, exigir
recusa puniria uma resposta correta. Reclassificados (id preservado, reescritos para ancorar
em artigo real validado top-5):

| id | era | virou | âncora |
|----|-----|-------|--------|
| `oos-prescricao-trabalhista` | refused | answered (labor) | CLT 11 |
| `oos-tra-01` | refused | answered (labor) | CLT 11 |
| `oos-tra-02` | refused | answered (labor) | CLT 59 |
| `oos-pen-03` | refused | answered (criminal) | CP 24 |

## 5. Métricas reais (`make eval` fake/offline, 216 perguntas)

Agregado:

| métrica | valor | threshold | resultado |
|---------|------:|----------:|-----------|
| retrieval_recall_at_5 | **0.9375** | 0.80 | PASS |
| citation_coverage | **1.0000** | 0.90 | PASS |
| unsupported_legal_claim_rate | **0.0000** | 0.05 | PASS |
| refusal_when_no_source_rate | **0.7000** | 0.90 | **FAIL** |

Recall@5 por área:

| área | recall@5 | found/expected |
|------|---------:|---------------:|
| civil | 1.0000 | 10/10 |
| criminal | 1.0000 | 11/11 |
| labor | 1.0000 | 13/13 |
| tax | 1.0000 | 10/10 |
| constitutional | 1.0000 | 10/10 |
| consumer | 0.9098 | 111/122 |

As **5 áreas novas têm recall@5 = 100%**. Os 11 misses são todos `cdc-*` pré-existentes do
consumer (não regressão desta fase). citation_coverage/unsupported = 1.0/0.0 por área
(answered não produz claim sem suporte sob o auditor + writer conservador).

## 6. Pendência (dono: answer) — refusal abaixo do gate, NÃO maquiada

`refusal_when_no_source_rate = 0.70 < 0.90`. **Causa-raiz medida** (não é defeito do golden):
o `AnswerWriter._MIN_SEMANTIC_SCORE = 0.29` foi calibrado para o corpus **só-CDC (130
chunks)**. No corpus de 6329 chunks o `FakeEmbeddingProvider` (bag-of-words léxico) produz
scores espúrios de 0.31–0.43 contra chunks irrelevantes para perguntas OOS, **acima** do
limiar, então o writer responde em vez de recusar. Exemplos medidos:

- `oos-declarar-bitcoin` → CTN art. 110 (sem= 0.376)
- `oos-tax-03` (ICMS importação) → CC art. 374 (sem= 0.425)
- `oos-pen-01` (interpretação STF feminicídio) → CC art. 2 (sem= 0.314)
- `oos-fam-02` (pensão alimentícia) → CC art. 2 (sem= 0.413)

12 OOS falham a recusa: `oos-declarar-bitcoin`, `oos-tax-02..05`, `oos-pen-01/02`,
`oos-fam-01..03`, `oos-suc-01`, `oos-divorcio-partilha`. São OOS **legítimos** (tributos
específicos não institui­dos no CTN; jurisprudência STF ausente; família/sucessões sem âncora
literal recuperável) — a resposta correta é recusar.

**Tarefa para o dono `answer` (não toquei `answer_writer.py`, fora do meu ownership):**
recalibrar o gate de grounding para o corpus multi-área — opções: (a) elevar/escalar
`_MIN_SEMANTIC_SCORE` em função do tamanho/densidade do corpus; (b) usar margem relativa
(top1 − top2) em vez de limiar absoluto; (c) estender o `_OOS_KEYWORDS`/classificador de área
para barrar tributos específicos / pedidos de jurisprudência STF ausente. Eu **não relaxei** o
threshold §36 nem o §2.2.

### Como o gate é ligado (documentação §36)
- `make eval` roda **strict por default** (todos os 4 thresholds) → atualmente FALHA por causa
  do refusal, sinalizando corretamente a pendência do `answer`.
- O gate de alucinação (`unsupported_legal_claim_rate ≤ 0.05`) é **sempre** aplicado e
  **passa** (0.0). Com `EVAL_GATE_STRICT=0` (bypass do orquestrador enquanto o `answer` é
  corrigido) o run sai 0 — verificado: "Gate (hallucination-only): PASSED".
- Recomendação ao orquestrador: rodar CI com `EVAL_GATE_STRICT=0` até o `answer` recalibrar o
  grounding; religar strict assim que o refusal voltar ≥ 0.90. A dívida está isolada ao par
  fake-provider × writer-threshold no caminho offline; com providers reais (eval-real) a
  similaridade tende a separar melhor OOS de in-scope.

## 7. eval-real (não roda aqui — sem credenciais)

O harness `eval-real` consome o **mesmo** golden multi-área (mesmo `load_golden()`), então não
precisou de mudança para aceitar as novas áreas. Comando:

```bash
make up                       # Postgres, Qdrant, Redis
make ingest-cdc && make ingest-codes && make ingest-case-law
curl -s -X DELETE "$QDRANT_URL/collections/legal_chunks"   # trocar de corpus/dim exige recriar
make index-corpus             # indexa os 6329 chunks
EVAL_PROVIDER=openai OPENAI_API_KEY=sk-... make eval-real   # ou EVAL_PROVIDER=local
```

NÃO executado neste ambiente (sem OPENAI_API_KEY/garantia de Docker).

## 8. Lint / mypy / testes (resultado real)

- `ruff check packages/evals data/seed` → **All checks passed!** (inclui C90 ≤ 10).
- `mypy packages/evals` → **Success: no issues found in 8 source files**.
- `pytest tests/evals` → **44 passed** (inclui 4 novos golden multi-área + 3 ajustados para
  refletir a dívida de refusal sem mascará-la).
- `make eval` (fake, offline) → executa; relatório `eval_report.{json,md}` gerado; ≥30 golden
  (216); todas as métricas calculadas; gate strict FALHA por refusal (pendência answer);
  gate de alucinação PASSA.

## 9. Arquivos
- `data/seed/questions/{civil,criminal,labor,tax,constitutional,out_of_scope}_golden.yaml` (novos).
- `data/seed/questions/consumer_golden.yaml` (4 reclassificações, ids preservados).
- `packages/evals/golden.py` (multi-arquivo + `area` + per-area stats).
- `packages/evals/{retrieval,citation,answer}_eval.py` (métricas por área).
- `packages/evals/{run_all,report}.py` (per-area no JSON/print/MD).
- `tests/evals/test_golden.py` (+4 testes: area, cobertura ≥10/área, metric_area, load single).
