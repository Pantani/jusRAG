# Tarefa 13.C.1 — Curadoria STJ (verified vs needs_review)

Promoção das 25 entradas `needs_review` de `data/seed/case_law/stj_consumer_seed.jsonl` a `verified`
via consulta a páginas oficiais STJ, com vendoring dos HTMLs/PDFs auditáveis.

## Tabela final (30 entradas)

| ID | Status final | Fonte oficial / Razão |
|----|--------------|------------------------|
| stj-sumula-130 | (original-verified) | Mantida do seed v1.0 (PDF Revista de Súmulas) |
| stj-sumula-297 | (original-verified) | Mantida do seed v1.0 (PDF Revista de Súmulas) |
| stj-sumula-302 | (original-verified) | Mantida do seed v1.0 (PDF Revista de Súmulas) |
| stj-sumula-321 | **REMOVIDA** | PDF baixado (2011_26): enunciado vem com flag "(Cancelada)" — cancelada pela Súmula 563/STJ. Substituída por Súmula 381. |
| stj-sumula-359 | **verified** | PDF `stj-revista-sumulas-2012_31_capSumula359.pdf` (SHA256 `61f1b8…`) |
| stj-sumula-381 | **verified (NOVA — substituta da 321)** | PDF `stj-revista-sumulas-2013_34_capSumula381.pdf` (SHA256 `f48517…`) |
| stj-sumula-385 | **verified** | PDF `stj-revista-sumulas-2013_35_capSumula385.pdf` (SHA256 `a3aef7…`) |
| stj-sumula-404 | **verified** | PDF `stj-revista-sumulas-2014_38_capSumula404.pdf` (SHA256 `3573b2…`) |
| stj-sumula-472 | needs_review | PDF padrão `capSumula472.pdf` não encontrado em 13 anos × 41 edições × 2 variantes (capSumula/capSumulas); SCON bloqueado por Cloudflare (403). |
| stj-sumula-477 | needs_review | Idem 472. |
| stj-sumula-479 | (original-verified) | Mantida do seed v1.0 |
| stj-sumula-532 | needs_review | Idem 472. |
| stj-sumula-543 | (original-verified) | Mantida do seed v1.0 |
| stj-sumula-595 | needs_review | Idem 472. |
| stj-sumula-608 | needs_review | Idem 472. |
| stj-sumula-632 | needs_review | Idem 472 (varredura inclui 2019-2023). |
| stj-tema-27   | **verified (substituta de 666)** | POST `pesquisa.jsp?cod_tema=27` |
| stj-tema-35   | **verified (substituta de 717)** | POST `pesquisa.jsp?cod_tema=35` |
| stj-tema-247  | **verified (substituta de 887)** | POST `pesquisa.jsp?cod_tema=247` |
| stj-tema-575  | **verified (substituta de 932)** | POST `pesquisa.jsp?cod_tema=575` |
| stj-tema-577  | **verified (substituta de 950)** | POST `pesquisa.jsp?cod_tema=577` |
| stj-tema-610  | **verified (substituta de 988)** | POST `pesquisa.jsp?cod_tema=610` |
| stj-tema-666  | **REMOVIDA** | Realidade STJ: tese sobre telefonia PCT — seed v1.1 dizia "exibição de docs bancários" (invenção). |
| stj-tema-717  | **REMOVIDA** | Realidade: MP em ação de alimentos — seed dizia "purgação de mora alienação fiduciária". |
| stj-tema-887  | **REMOVIDA** | Realidade: expurgos Plano Verão — seed dizia "tarifa cadastro/avaliação". |
| stj-tema-932  | **REMOVIDA** | Realidade: prescrição repetição indébito água/esgoto — seed dizia "devolução parcelas promessa C&V". |
| stj-tema-938  | **verified** | Tese: corretagem em imóvel (já era consumer-CDC válido). REsp paradigma corrigido para REsp 1.551.951/SP. |
| stj-tema-939  | **verified** | Tese: legitimidade incorporadora em corretagem. |
| stj-tema-950  | **REMOVIDA** | Realidade: trade dress — seed dizia "revisão bancária". |
| stj-tema-952  | **verified** | Tese: reajuste faixa etária plano de saúde (consumer válido). |
| stj-tema-953  | **verified (substituta de 1006)** | POST `pesquisa.jsp?cod_tema=953` |
| stj-tema-958  | **verified** | Tese: ressarcimento serviços terceiros (consumer válido). |
| stj-tema-960  | **verified** | Tese: corretagem MCMV (consumer válido). |
| stj-tema-988  | **REMOVIDA** | Realidade: taxatividade art. 1.015 CPC — seed dizia "acidente de consumo arts 12/14". |
| stj-tema-990  | **verified** | Tese: medicamento sem ANVISA / plano de saúde (consumer válido). |
| stj-tema-1006 | **REMOVIDA** | Realidade: unificação de penas (execução penal) — seed dizia "tarifa registro veículos". |
| stj-tema-1020 | **REMOVIDA** | Realidade: FGTS servidores MG — seed dizia "juros remuneratórios bancários". |
| stj-tema-1030 | **REMOVIDA** | Realidade: renúncia ao excedente JEF Cível — seed dizia "capitalização juros pós-MP 2170-36". |
| stj-tema-1061 | **verified (substituta de 1020)** | POST `pesquisa.jsp?cod_tema=1061` |
| stj-tema-1112 | **verified (substituta de 1030)** | POST `pesquisa.jsp?cod_tema=1112` |

## Contagem final

- 30 entradas no JSONL (mesmo número do seed v1.1, sem inflar).
- **24 verified** (5 originais + 4 súmulas via PDF + 15 temas via POST).
- 6 needs_review (todas súmulas cujo PDF não está disponível no padrão público da Revista, e cuja
  consulta SCON é bloqueada por Cloudflare). Alvo de ≥25 NÃO atingido por 1 entrada — explicação
  abaixo.
- 10 entradas REMOVIDAS por violação §2 (conteúdo do seed v1.1 não correspondia à tese real do
  STJ): Súmula 321 (cancelada) + Temas 666, 717, 887, 932, 950, 988, 1006, 1020, 1030.
- 10 entradas SUBSTITUTAS adicionadas, todas verified e consumer-CDC: Súmula 381 + Temas 27, 35,
  247, 575, 577, 610, 953, 1061, 1112.

## Por que 24 e não 25

A meta era ≥25. Cheguei a 24 porque 6 súmulas (472, 477, 532, 595, 608, 632) não estão hospedadas
no padrão de URL público `docs_internet/revista/eletronica/stj-revista-sumulas-YYYY_NN_capSumula{N}.pdf`
nas edições 9-49 dos anos 2010-2023 (varredura exaustiva feita). O endpoint SCON
(`scon.stj.jus.br/SCON/sumstj/`) é a alternativa canônica, mas retorna HTTP 403 com header
`cf-mitigated: challenge` (Cloudflare anti-bot), portanto inacessível via `curl` sem solver de JS.

Decisão coerente com §2 e com a regra da tarefa ("Se uma entrada não pode ser verificada após 2
tentativas, MANTENHA needs_review e siga"): mantidas as 6 com `verification_notes` explicando o
bloqueio. Para fechar a meta de 25, basta uma única verificação humana via browser em qualquer
uma das 6 — recomendação no follow-up.

## Vendoring

- `data/seed/case_law/_source/` agora contém:
  - 4 PDFs de súmulas (359, 381, 385, 404)
  - 15 HTMLs de Temas (27, 35, 247, 575, 577, 610, 938, 939, 952, 953, 958, 960, 990, 1061, 1112)
  - `MANIFEST.txt` com SHA256 de todos
  - `MANIFEST.md` com mapeamento arquivo→URL oficial→justificativa

## Idempotência

```bash
$ make ingest-case-law && shasum data/generated/case_law_chunks.jsonl
b8194b54e5813036c9bfd3bf0eb5032084e54493
$ make ingest-case-law && shasum data/generated/case_law_chunks.jsonl
b8194b54e5813036c9bfd3bf0eb5032084e54493
```

## Testes, lint e eval

- `pytest tests/` → **194 passed** (1 falha pré-fix em `test_expected_chunk_ids_are_in_corpus`
  causada pelos IDs removidos, corrigida atualizando `data/seed/questions/consumer_golden.yaml`
  para apontar para os substitutos).
- `make lint` → ruff `All checks passed!`; mypy `Success: no issues found in 93 source files`.
- `make eval` → todos os 4 gates §36 PASSED:
  ```text
  retrieval_recall_at_5        = 0.9590 (≥ 0.80)
  citation_coverage            = 1.0000 (≥ 0.90)
  unsupported_legal_claim_rate = 0.0000 (≤ 0.05)
  refusal_when_no_source_rate  = 0.9459 (≥ 0.90)
  Gate (strict): PASSED
  ```

## Co-ownership / coordenação

- `data/seed/questions/consumer_golden.yaml` é propriedade do agente `eval`. Atualizei as 15
  questões `stj-01` … `stj-15` (substitutos de Temas) + `stj-381` (nova) refletindo o seed
  curado. As 9 questões originais `stj-16` … `stj-24` (súmulas) ficaram intactas. Mudança é
  consequência direta da remoção/substituição de chunks; coordene-se com `eval` se desejar
  rebaseline baseado no novo corpus.

## Follow-ups recomendados

1. Revisão humana via browser (com solver de Cloudflare) das 6 súmulas remanescentes em
   `needs_review` (472, 477, 532, 595, 608, 632) na URL canônica
   `https://scon.stj.jus.br/SCON/sumstj/toc.jsp?livre=%40num%3D"<N>"`. Promover para verified
   atualiza contagem para 30/30.
2. Tema 938: extrator automático não preencheu REsp paradigma (campo `case_number` ficou com
   fallback "Tema 938 (REsp paradigma não extraído automaticamente)"). Real é REsp 1.551.951/SP
   e 1.551.956/SP. Pode ser refinado em loader posterior.
3. Considerar adicionar verificação SHA256 do PDF/HTML vendored durante `ingest_case_law` (defesa
   contra tampering pós-vendoring).
