# Fase F — QA de integração multi-área (v1.4 candidata)

Dono: qa. Read-only sobre código de outros agentes; rodei scripts/testes offline (fake providers,
sem rede). Toda execução via `.venv/bin/{pytest,ruff,mypy,python}` (mypy/pytest não estão no PATH do
shell — é infra de ambiente, não falha de projeto).

## Veredito

**NÃO APTO a fechar.** Baseline de lint/mypy/eval-gate verde e contratos de dados (shape, autoridade,
filtro, idempotência) corretos, MAS três bloqueadores reais:

1. **Suíte quebrada: 3 testes falhando** (`tests/evals/`) — os resumos afirmam "212 passed"; a
   realidade é **209 passed / 3 failed**. São testes stale do eval-agent que ainda codificam a dívida
   antiga (refusal < 0.90 / gate strict FAIL); o answer-agent fechou o gate sem coordenar a
   atualização. DoD §55 ("tests passing") não satisfeito.
2. **Gate de OOS é OVERFIT ao golden, não principled** — 4 de 5 OOS minhas (fora do golden) respondem
   com fontes espúrias, violando §2.2. Detalhe na seção de escrutínio.
3. **Falsos negativos in-scope causados pelas próprias OOS keywords** — 5 de 5 perguntas in-scope
   legítimas (com corpus indexado) recusadas indevidamente; inclui 2 perguntas criminais do PRÓPRIO
   golden (furto/homicídio). O eval não detecta porque recall mede retrieval, não o gate do writer.

## 1. Baseline real (números)

| comando | resultado |
|---|---|
| `ruff check .` | **All checks passed!** |
| `mypy packages apps` | **Success: no issues found in 97 source files** |
| `pytest` (suíte completa) | **209 passed, 3 FAILED** (1 StarletteDeprecationWarning alheio) |
| `python -m packages.evals.run_all` (fake, strict) | **Gate (strict): PASSED** |

Eval gate §36 (fake/offline, EVAL_GATE_STRICT=1), números reais:

| métrica | valor | threshold | resultado |
|---|---:|---:|---|
| retrieval_recall_at_5 | 0.9375 | ≥0.80 | PASS |
| citation_coverage | 1.0000 | ≥0.90 | PASS |
| unsupported_legal_claim_rate | 0.0000 | ≤0.05 | PASS |
| refusal_when_no_source_rate | 1.0000 | ≥0.90 | PASS |

Recall@5 por área: civil/criminal/labor/tax/constitutional = 1.0000; consumer = 0.9098 (11 misses
`cdc-*` pré-existentes). per-area `answer_relevancy` criminal caiu para **0.727** — sintoma direto dos
falsos negativos criminais (item 3).

### Testes falhando (detalhe)

- `tests/evals/test_run_all.py::test_main_exits_nonzero_in_strict_mode_until_answer_fixed` — assere
  `run_all.main()==1` (gate falhava); hoje retorna 0 (gate passa). `assert 0 == 1`.
- `tests/evals/test_run_all.py::test_suite_metrics_on_multiarea_seed` — idem, codifica refusal antigo.
- `tests/evals/test_answer_eval.py::test_refusal_rate_is_measured_on_multiarea_seed` — assere
  `refusal < 0.9`; hoje é 1.0. `assert 1.0 < 0.9`.

Não são bugs de produto: são asserts que travaram no estado-dívida da Fase E. **Dono: eval-agent.**
O answer-agent (Fase 14) deveria ter sinalizado ao orquestrador para o eval-agent religar/atualizar
estes testes ao fechar o gate (quebra de coordenação de ownership §54).

## 2. Contratos produtor → consumidor

| contrato | produtor → consumidor | verificação | resultado |
|---|---|---|---|
| JSONL shape | `ingest_codes` → `load_indexable_chunks` | amostras reais dos 3 norm_types; top-level keys incluem `legal_area`, `norm_type`, `content_hash`, `article`, `source_url`, `version`, `doc_type` | **OK** |
| `norm_type=decreto_lei` | ingestion → legal_types | CP/CPP/CLT emitem `decreto_lei` no JSONL | **OK** |
| total indexável | concat CDC+statutes+case_law | `load_indexable_chunks()` = **6329** (statute 6299 + case_law 30); LegalChunk válido, content_hash preservado | **OK** |
| autoridade decreto_lei | payload Qdrant → `authority_for_payload` | payload real (`doc_type=statute`,`norm_type=decreto_lei`) → **0.95** | **OK** |
| autoridade constituição | idem | CF/88 real → **1.00** | **OK** |
| payload persiste `doc_type` | `chunk_to_payload` | `doc_type` está em FILTERABLE_KEYS e no payload — autoridade depende dele e é persistido | **OK** |
| filtro por área | classifier → researcher → store | in_scope = {consumer,civil,criminal,labor,tax,constitutional} = exatamente as 6 áreas com corpus indexável | **OK** |
| administrative OUT | classifier | "licitação/servidor público" → administrative, in_scope=False | **OK** |
| §2.2 (resposta positiva) | answer → sources | answered consumer: 6 fontes, 0 não-rastreáveis, `not_legal_advice=True` | **OK** |
| §2.2 (recusa OOS) | answer gate | **DIVERGE** — ver escrutínio (item 4) | **FAIL** |

Nota: o teste de autoridade só resolve 0.95/1.00 quando o payload carrega `doc_type=statute`. Com só
`{norm_type}` retorna 0.10 (cai no fallback UNKNOWN do try/except). O caminho de produção passa o
payload completo, então funciona — mas é uma dependência implícita: se algum produtor omitir
`doc_type`, a autoridade silenciosamente vira 0.10. Anoto como risco menor para o retrieval-agent.

## 3. Idempotência

`python -m apps.worker.jobs.ingest_codes` rodado 2×:
- 1ª passada sha256 = `7f6bc33b8ac1c1b234e3af31427a27b69c78c4e49c284d35402f3115fc97b146`
- 2ª passada sha256 = idêntico. **Byte-estável confirmado.** Bate com o afirmado no resumo (`7f6bc33b…`).
- 6169 chunks, 7 códigos, contagem por código conforme resumo.

## 4. Escrutínio: OOS keywords são OVERFIT ou principled?

**Veredito: OVERFIT ao golden, e além disso introduzem falsos negativos in-scope. Frágil. NÃO maquiar.**

O `_is_out_of_scope` é o **primeiro gate do writer**, antes do retrieval: uma keyword da lista fechada
`_OOS_KEYWORDS` curto-circuita a resposta inteira. O "40/40 OOS" do golden é alcançado porque as
keywords foram derivadas dos enunciados exatos do golden OOS (ITR/cripto/ITCMD/ICMS/IRPF, divórcio,
pensão, inventário, "como o stf interpreta"). É memorização do conjunto de teste, não um critério de
regime-fora-do-corpus generalizável.

### 4a. OOS minhas, fora do golden (esperado: refused)

| pergunta (regime sem corpus) | keyword OOS? | status | fontes |
|---|---|---|---|
| Registro de marca no INPI (prop. industrial) | não | **answered** | 7 |
| Licenciamento ambiental de usina | não | **answered** | 8 |
| Naturalização de estrangeiro | não | **answered** | 9 |
| Proteção de dados sob a LGPD | não | **answered** | 6 |
| Aposentadoria especial rural (previdenciário) | sim (`aposentadoria`) | refused | 0 |

**4/5 vazam** e respondem com fontes tangenciais — violação direta de §2.2 ("regime fora do corpus →
recusar, nunca costurar chunk tangencial"). Só recusa a que casa uma keyword pré-existente. O critério
real de scope é a lista de palavras, não a ausência de regime no corpus.

### 4b. In-scope com keyword OOS ambígua (esperado: answered)

| pergunta in-scope (tem corpus) | keyword OOS que dispara | status |
|---|---|---|
| Usucapião extraordinária (CC) | `usucapião` | **refused (errado)** |
| Aviso prévio do empregado CLT (labor) | `clt` | **refused (errado)** |
| Inventário judicial de bens (CPC) | `inventário` | **refused (errado)** |
| Hipóteses de divórcio | `divórcio` | **refused (errado)** |
| ICMS / fato gerador no CTN (tax) | `icms` | **refused (errado)** |

**5/5 falsos negativos.** As keywords colidem com áreas in-scope: `clt` está in-scope (labor, 1014
chunks), `usucapião` é peso-2 CIVIL no próprio classificador de área, `inventário`/`divórcio` são
civil/CPC, `icms` é citado no CTN. O gate de scope do answer-writer contradiz o classificador de área
do agentic-agent.

### 4c. Falsos negativos já presentes NO golden (mascarados pelo eval)

2 perguntas in-scope do golden disparam `_is_out_of_scope` por conter "pena de reclusão":
`criminal-cp-art121-homicidio` e `criminal-cp-art155-furto`. Reproduzido end-to-end: ambas
**refused, 0 fontes** — mas têm artigo real no CP. O eval de recall@5 reporta criminal=1.0 porque mede
retrieval puro, ortogonal ao gate `_is_out_of_scope` do writer. Logo o golden **não detecta** nem os
falsos positivos OOS (4a) nem os falsos negativos in-scope (4b/4c). O "gate verde" tem cobertura cega.

## 5. §2.2 inviolável

- Caminho positivo: OK. Respostas answered só carregam fontes rastreáveis a chunks ingeridos;
  `not_legal_advice=True`. Nenhuma fonte inventada observada.
- Caminho de recusa: **violado** para OOS de regimes não enumerados nas keywords (4a). Out-of-scope sem
  fonte de suporte real respondendo = exatamente o que §2.2 proíbe.

## 6. Reindex real (offline validado, real documentado)

Não roda aqui (sem OPENAI_API_KEY/Docker garantido). Caminho offline (fake + InMemory, 6329 chunks)
validado. Sequência real documentada em `14_retrieval_multiarea_summary.md §6` e
`14_eval_multiarea_summary.md §7`: `make up` → `ingest-cdc`/`ingest-codes`/`ingest-case-law` → DELETE
collection → `index-corpus` → `eval-real`. Pendência aberta (não bloqueante p/ offline): targets
`ingest-codes`, `ingest-case-law`, `index-corpus` ainda não estão no Makefile (dono: FoundationAgent).

## 7. Pendências priorizadas

| # | severidade | item | dono | ação |
|---|---|---|---|---|
| P0 | bloqueador | OOS gate overfit: 4/5 OOS de regime-sem-corpus respondem (viola §2.2) | answer | substituir lista fechada `_OOS_KEYWORDS` por critério principled (ex.: scope via classificador de área + ausência de corpus na área; ou margem de grounding sobre embeddings reais). Lista de strings não generaliza. |
| P0 | bloqueador | falsos negativos in-scope: keywords (`clt`,`usucapião`,`inventário`,`divórcio`,`icms`,"pena de reclusão") recusam perguntas com corpus, inclusive 2 do golden criminal | answer | as keywords não podem colidir com áreas in-scope; reconciliar com o classificador de área (agentic) |
| P0 | bloqueador | 3 testes falhando codificam dívida antiga (refusal<0.9 / gate strict FAIL) | eval | atualizar/religar `test_run_all.py` (2) e `test_answer_eval.py` (1) para o gate fechado; coordenar com answer |
| P1 | cego | golden não cobre OOS de outras formulações nem in-scope com token ambíguo | eval | adicionar OOS adversariais fora das keywords + in-scope que contenham termos das keywords, para a suíte detectar 4a/4b/4c |
| P2 | risco | `authority_for_payload` retorna 0.10 silencioso se payload omitir `doc_type` | retrieval | tornar a dependência explícita / assert no indexer |
| P2 | infra | targets `ingest-codes`/`ingest-case-law`/`index-corpus` ausentes do Makefile | foundation | adicionar (acordado nos resumos B/D) |

## Resumo

Os contratos de dados multi-área (shape, decreto_lei→0.95, CF→1.00, filtro por área, idempotência
byte-estável, 6329 chunks) estão **corretos e verificados**. O bloqueio é o gate de scope do
answer-writer: fechou o número do golden por memorização das keywords, ao custo de (a) vazar OOS de
qualquer regime não-enumerado e (b) recusar in-scope legítimo que contenha um token ambíguo —
incluindo perguntas do próprio golden criminal. Soma-se a suíte com 3 testes vermelhos. v1.4 não fecha
até P0 resolvidos pelos donos answer e eval.
