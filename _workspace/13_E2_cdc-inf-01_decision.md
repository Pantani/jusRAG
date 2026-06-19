# Phase 13.E.2 — Destino do retrieval miss residual `cdc-inf-01`

## Entrada

```yaml
- id: cdc-inf-01
  question: "comprei um celular novo e veio com defeito de fábrica, e agora?"
  expected_chunk_ids: [cdc-8078-1990-art-18]
  expected_behavior: answered
  expected_articles: ["18"]
```

Query coloquial, sem âncora léxica de citação (não cita "art. 18" nem termo verbatim
de inciso), legitimamente in-scope CDC (vício/defeito de produto; art. 18 é núcleo do
regime de vício de qualidade). Diagnóstico D.3 já estabelecido: art-18 fica em **rank 8
com OpenAI embeddings**; gate §36 PASSED com folga (recall@5 = 0.9918 ≥ 0.80).

## Diagnóstico confirmado (data-driven)

Causa-raiz: **gap léxico-semântico de sinônimo**. A query usa "defeito de fábrica".
No CDC esse evento é tipificado como *vício de qualidade* (art. 18), termo que NÃO
aparece na query. "Defeito" puxa art-12 (fato/defeito do produto — responsabilidade
por acidente de consumo), que é semanticamente vizinho mas é o artigo errado. Não há
ponte léxica "defeito de fábrica" → "vício" em nenhuma das duas modalidades.

### Probe 1 — hybrid mitiga? (corpus real 130 chunks, fake provider determinístico)

| Configuração | rank de art-18 |
| --- | --- |
| dense-only (fake emb) | 6 |
| hybrid 0.7/0.3 (defaults `Settings`) | **6** (não move) |
| hybrid 0.5/0.5 | 5 (marginal, e distorce o topo: art-104-a sobe a rank 1) |

BM25-only coloca art-18 **fora do top-8** (top-1 é art-104-a). Motivo: a query
coloquial não compartilha termos raros com art-18; BM25 reforça artigos que casam
"defeito"/"produto"/"novo" lexicalmente, não o art. 18. **Hybrid NÃO é mitigação
para este caso** — no peso default (0.7/0.3) é inerte, e só em 0.5/0.5 ganha 1 posição
às custas de degradar o ranking dos demais. Conclusão empírica: o sinal que falta é
de **vocabulário**, não de modalidade léxica vs densa.

> Nota metodológica: o probe usa fake embeddings (lexicais). O rank absoluto difere do
> OpenAI (rank 8 no eval-real), mas a **direção** do efeito BM25 é representativa: BM25
> opera sobre os mesmos tokens superficiais que já falham em apontar art-18.

### Probe 2 — qual é o fix real? (query expansion, dense-only fake emb)

| Query | rank de art-18 |
| --- | --- |
| original ("...defeito de fábrica...") | 6 |
| + "vício de qualidade do produto, substituição reparo abatimento" | **2** |
| "produto com vício de qualidade troca conserto prazo 30 dias" | 4 |

Injetar o sinônimo jurídico "vício de qualidade" recupera art-18 ao top-3 com dense
puro. O fix real é **query expansion** (mapa sinônimo coloquial→jurídico:
"defeito de fábrica" → "vício de qualidade"), de escopo de outra fase
(QueryAnalyzer / expansão de termos), não de ranking nem de fusão BM25.

## Decisão: (c) known-limitation, SEM mitigação por hybrid

Justificativa:

- **(b) OOS está descartada** — a query tem fonte CDC clara (art. 18). Marcá-la OOS
  violaria §2 (separação de escopo) e mascararia uma capacidade que queremos cobrir.
- **(a) reescrever a query está descartada** — queries coloquiais ("comprei X e veio
  com defeito, e agora?") são exatamente o caso de uso real-world alvo. Reescrever para
  vocabulário jurídico reduziria o realismo do golden e esconderia a limitação real.
- **(c) known-limitation é a escolha defensável** — o gate §36 já PASSA com folga
  (recall@5 = 0.9918), 1 miss residual em query adversarialmente coloquial não relaxa
  threshold e não exige inventar fonte. Documenta-se a causa (gap de sinônimo) e o fix
  de escopo futuro (query expansion no QueryAnalyzer).

**Hybrid NÃO conta como mitigação implementada** para este caso: o probe mostra que no
peso default é inerte e que BM25 não tem como apontar art-18 a partir do vocabulário da
query. (O caminho hybrid permanece útil e opt-in para queries com âncora léxica/verbatim,
e.g. os casos art-39 do D.3 — apenas não resolve `cdc-inf-01`.)

## Fix real (escopo de fase futura, fora de E.2)

Query expansion no `QueryAnalyzer`: dicionário sinônimo coloquial→técnico do CDC
(`defeito de fábrica`/`veio com defeito` → `vício de qualidade`;
`não funciona`/`quebrou` → `vício do produto`). Probe 2 confirma que isso sozinho leva
art-18 a rank 2 no dense. Ownership: query_analyzer (RetrievalAgent) + curadoria de
termos (LegalDomain). Não implementado aqui para manter o diff de E.2 nulo no código.

## Não alterado

- `data/seed/questions/consumer_golden.yaml` — intacto (não relaxa §36, não renumera ids).
- Thresholds — intactos.
- Código de ranking/retriever — nenhum diff (decisão é documental).

## Validações

- `make test` → 203 passed.
- `make lint` → ruff + mypy strict OK (94 files).
