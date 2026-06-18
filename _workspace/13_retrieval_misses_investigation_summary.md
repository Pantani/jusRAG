# Phase 13.D.3 — Retrieval Misses Investigation (OpenAI baseline)

## TL;DR

Baseline C.3 (commit a7122ac): openai recall@5 = **0.9754** com 3 misses adversariais
(cdc-pre-02, cdc-ab-04, cdc-ab-08). Investigação revelou um **bug de truncamento no
loader Planalto** afetando o caput de praticamente todos os artigos do CDC + sinal
fraco para queries que citam verbatim um inciso de artigo longo (art. 39 tem 14
incisos e ~2,5k chars: o centróide semântico dilui contra a query).

Pós-fix: openai recall@5 = **0.9918** (+1,64pp), refusal_when_no_source_rate
**1.0000** (+8,11pp), todos os gates §36 PASSED. Único miss residual é cdc-inf-01
(query coloquial fora do escopo das 3 originais).

## Failing cases — antes vs depois

| query_id | question (resumida) | expected | rank antes (top-3) | rank depois (top-3) | diagnóstico | fix |
| --- | --- | --- | --- | --- | --- | --- |
| cdc-pre-02 | "Prazo de prescrição quinquenal CDC pretensão reparação danos fato do produto" | art-27 | **out of top-50** (caput truncado: chunk continha só "...causados por fato", o trecho "do produto ou do serviço prevista..." foi descartado) | **rank 1** (sem=0.6500, score=0.6450). Top-3: art-27, art-25, art-100 | (a) chunker — `_ARTICLE_RE` no `planalto_html.py` capturava só a 1ª linha do `<p>` contendo o caput; demais linhas eram silenciosamente descartadas | partition do paragraph: linha 1 vai para `_emit_article`, restante vai para `_emit_article_body` |
| cdc-ab-04 | "Prevalecer-se da fraqueza ou ignorância do consumidor tendo em vista sua idade saúde conhecimento" | art-39 | rank 17 (art. 39 é o maior do CDC; query é literalmente o inciso IV, mas a semântica do art. inteiro dilui) | **rank 1** (sem=0.4703, score=0.6192 — phrase_overlap +0,10). Top-3: art-39, art-68, art-23 | (b) gap léxico-estrutural: artigo gigante com 14 incisos, query bate um único inciso | adicionado `phrase_overlap` (4-gram verbatim) no slot CITATION_WEIGHT (max com exact_citation_match — pesos §38 inalterados); `_CANDIDATE_MULTIPLIER` 3→6 / `_MIN_CANDIDATES` 16→32 para garantir over-fetch suficiente |
| cdc-ab-08 | "Recusar a venda de bens... pronto pagamento" (texto do inciso IX, art. 39) | art-39 | out of top-5 (mesmo motivo: art. 39 grande) | **rank 1** (sem=0.5331, score=0.6632 — phrase_overlap +0,10). Top-3: art-39, art-53, art-54-C | (b) idem ab-04 — verbatim do inciso IX | mesmo fix |

Miss residual:

- **cdc-inf-01** ("comprei um celular novo e veio com defeito de fábrica, e agora?" → art-18):
  query coloquial, sem âncora léxica nem citação. Art-18 fica em rank 8 (semantic 0,40)
  porque "defeito" puxa art-12; "vício" só aparece no caput de art-18, sem alinhamento
  semântico forte com a query informal. Diagnóstico (b), mas fix exigiria query
  expansion (sinônimos "defeito de fábrica" → "vício de qualidade") ou hybrid
  BM25 — escopo de outra fase. Gate §36 já PASSED com folga (0.9918 ≥ 0.80).

## Diffs aplicados (ownership respeitada)

1. `packages/ingestion/loaders/planalto_html.py` — em `_convert_paragraphs`, antes de
   `_ARTICLE_RE.match(text)` separar `first_line, _, remainder = text.partition("\n")`
   e emitir `remainder` como `_emit_article_body` para preservar caputs multi-linha.
   **Impacto**: ~93 artigos do CDC tinham o caput truncado na 1ª linha do `<p>` HTML
   do Planalto; agora o texto integral chega ao chunker (130 chunks idempotentes
   mantidos; `make ingest-cdc` regenera `cdc.md` deterministicamente).

2. `packages/rag/legal_ranker.py` — adicionado `phrase_overlap(query, chunk_text,
   window=4)`: 1.0 quando qualquer n-grama de 4 tokens da query aparece verbatim no
   chunk. `composite_score` agora aceita `query: str = ""` (kwarg-only, default
   compatível) e usa `citation = max(exact_citation_match, phrase_overlap)` — pesos
   §38 (0.70/0.20/0.10) **não mudam**, o slot CITATION_WEIGHT passa a carregar dois
   sinais alternativos.

3. `packages/rag/retriever.py` — `composite_score(hit, requested_article, query=query)`
   passa a query; `_CANDIDATE_MULTIPLIER 3→6`, `_MIN_CANDIDATES 16→32` para que o
   over-fetch cubra artigos longos (art. 39 estava em rank 17, agora entra no
   pool de re-ranking).

4. `data/seed/cdc/cdc.md` + `data/generated/cdc_chunks.jsonl` — regenerados pela
   pipeline (idempotentes, byte-stable).

5. Qdrant `legal_chunks` reindexado (160 chunks, openai text-embedding-3-small 1536d).

**Não tocado**: `packages/answer/*`, `packages/llm/*`, `packages/evals/*`, Makefile
(ownership de D.2). `data/seed/questions/consumer_golden.yaml` **não foi alterado**
— nenhum diagnóstico (d) confirmado.

## Métricas — eval-real openai (gate §36 strict)

| Métrica | Baseline (C.3, a7122ac) | Pós-fix (D.3) | Threshold | Δ |
| --- | --- | --- | --- | --- |
| retrieval_recall_at_5 | 0.9754 | **0.9918** | 0.80 | +0.0164 |
| retrieval_precision_at_5 | ~0.1951 | 0.1984 | — | +0.0033 |
| citation_coverage | 1.0000 | 1.0000 | 0.90 | = |
| unsupported_legal_claim_rate | 0.0000 | 0.0000 | 0.05 | = |
| refusal_when_no_source_rate | 0.9189 | **1.0000** | 0.90 | +0.0811 |
| answer_relevancy (heur.) | 0.9836 | (não regrediu) | — | — |
| faithfulness (heur.) | 0.8689 | (não regrediu) | — | — |
| **Gate strict** | PASSED | **PASSED** | — | — |
| Retrieval fails | 3 (pre-02, ab-04, ab-08) | 1 (inf-01) | — | -2 |
| Refusal fails | 3 (oos-emp-01, oos-adm-02, oos-pre-02) | 0 | — | -3 |

Custo do eval-real (ordem de grandeza, igual ao C.3 — mesmas chamadas):

- Embeddings: 159 queries × ~50 tokens × $0.02/1M ≈ **$0.0002**
- Chat (gpt-4o-mini, baseline): 159 chamadas × ~3,6k tokens médios ≈ **$0.10–0.15**
- Reindexação: 160 chunks × ~250 tokens × $0.02/1M ≈ **$0.001**
- **Total por execução**: **~$0.15** (dominado por chat; 1 execução final).

## Validações

- `pytest tests/` → **202 passed** (todos os 4 testes de eval que estavam vermelhos
  no estado de chegada agora passam — phrase_overlap recuperou refusal no fake).
- `ruff check packages/rag/legal_ranker.py packages/rag/retriever.py packages/ingestion/loaders/planalto_html.py` → **All checks passed**.
- `EVAL_PROVIDER=openai make eval-real` → **Gate (strict): PASSED**.
- Sem regressão em `make eval` (fake providers).
