# Tarefa 13.D.1 — Desbloqueio Cloudflare das 6 súmulas STJ pendentes

Tentativa de promover a `verified` as 6 entradas STJ marcadas `needs_review` em
`data/seed/case_law/stj_consumer_seed.jsonl` que ficaram bloqueadas em C.1 por Cloudflare no SCON.

## Resultado: 3 promovidas via Wayback / 3 ainda needs_review (bloqueio físico documentado)

| Súmula | Status final | Fonte | Hash do vendoring |
|--------|--------------|-------|--------------------|
| 472 | **verified** | Wayback Machine snapshot 2022-11-21 do SCON | `bf851748…` |
| 477 | needs_review (`verification_blocked: cloudflare_scon`) | — | snapshot Wayback retornou 0 resultados |
| 532 | needs_review (`verification_blocked: cloudflare_scon`) | — | snapshot Wayback retornou 0 resultados |
| 595 | **verified** | Wayback Machine snapshot 2022-11-21 do SCON | `9eb20c28…` |
| 608 | **verified** | Wayback Machine snapshot 2022-11-21 do SCON | `c143d3bc…` |
| 632 | needs_review (`verification_blocked: cloudflare_scon`) | — | snapshot Wayback retornou 0 resultados |

**Total corpus STJ pós-D.1:** 27 efetivamente verificadas (22 com `verification_status: verified`
explícito + 5 originais do seed v1.0 sem o campo) / **3 needs_review** com tarefa humana documentada.

## Estratégias tentadas

| # | Estratégia | Resultado |
|---|-----------|-----------|
| 1 | curl com headers Chrome realistas (UA moderno, Accept-Language pt-BR, Referer https://www.stj.jus.br/, cookie jar, `--compressed`) contra `scon.stj.jus.br/SCON/sumstj/toc.jsp?livre=%40num%3D"<N>"` | **falhou** — HTTP 403 para todas 6, `cf-mitigated: challenge` no header de resposta |
| 2 | PDF Revista de Súmulas `docs_internet/revista/eletronica/stj-revista-sumulas-{YYYY}_{NN}_capSumula{N}.pdf` (sweep adicional 2010-2023 × 41 edições × variantes capSumula/capSumulas) | **falhou** — C.1 já havia exausto; portal de publicações institucionais foi migrado para BDJur em jan/2026 (redirect 302 da URL `publicacaoinstitucional/index.php/sumstj/issue/archive` confirma) |
| 3a | Wayback CDX API para `scon.stj.jus.br/SCON/sumstj/toc.jsp?livre='{N}'.num.` | **parcial** — 6/6 snapshots HTTP 200 de 2022-11-21 encontrados |
| 3b | Download `id_` (raw, sem toolbar) de cada snapshot | **3/6 com enunciado literal** (472, 595, 608); 3/6 capturaram apenas a página de UI sem dados ("Em vigor (0), Canceladas (0)") porque o Wayback não rendeu o resultado dinâmico da busca |
| 3c | Wayback CDX para PDFs em `stj.jus.br/publicacaoinstitucional/` (2682 PDFs indexados) | **falhou** — nenhum hit para `capSumula{477,532,632}` |
| 3d | Wayback CDX para BDJur e DJe | **falhou** — 0 snapshots para esses paths |
| 4 | DJe direto (`dje.stj.jus.br/index.action?numSumula={N}`) | **falhou** — connection refused (HTTP 000) |
| 5 | BDJur simple-search (`bdjur.stj.jus.br/jspui/simple-search`) | **falhou** — HTTP 403 Cloudflare |
| 5b | Portal STJ Notícias (`www.stj.jus.br/sites/portalp/.../Noticias.aspx`) | **falhou** — HTTP 403 Cloudflare |

## Validação dos snapshots verified (472, 595, 608)

Cada `wayback_{N}.html` foi decodificado em latin-1 (encoding original do SCON), tags HTML
strippadas, e o texto comparado com o campo `ementa` do seed. Match exato em todos os 3 casos:

```text
=== Súmula 472 === EMENTA MATCH: True
=== Súmula 595 === EMENTA MATCH: True
=== Súmula 608 === EMENTA MATCH: True
```

`verification_notes` no JSONL inclui URL do snapshot, data, SHA256 do arquivo vendored e caminho
local.

## Por que 477/532/632 não bateram no Wayback

Os snapshots dessas 3 datam de 2022-11-21 mas correspondem a páginas em que a busca dinâmica
não retornou resultados (provavelmente um robot do Wayback acessou a URL sem manter o `livre`
expandindo via JS, ou houve cache miss no backend SCON na hora da captura). O HTML tem apenas
o chrome da página + "Resultados Situação: Em vigor (0), Canceladas (0)" — confirmado
inspecionando ~6kB de texto pós-strip de cada um.

Snapshots preservados em `_source/cloudflare_unblock/wayback_{477,532,632}.html` como **prova
documental da tentativa**, com hashes registrados em `MANIFEST.txt`.

## Mudanças no seed JSONL

- 472, 595, 608: `verification_status` → `"verified"`; `verification_notes` reescrito com URL
  Wayback + sha256 + caminho do snapshot.
- 477, 532, 632: `verification_status` permanece `"needs_review"`; novo campo
  `verification_blocked: "cloudflare_scon"`; `verification_notes` reescrito documentando todos
  os endpoints testados (SCON, BDJur, portal, DJe, Wayback PDF/CDX) e apontando para
  `_workspace/13_human_curation_task_v1.3.md`.

## Idempotência preservada

```bash
$ make ingest-case-law && shasum data/generated/case_law_chunks.jsonl
... Ingested 30 case_law chunk(s) ...
d2d058ca48efef5163a069a2f52769bd08c1a551  data/generated/case_law_chunks.jsonl
$ make ingest-case-law && shasum data/generated/case_law_chunks.jsonl
d2d058ca48efef5163a069a2f52769bd08c1a551  data/generated/case_law_chunks.jsonl
```

Os 30 chunks (24 súmulas + 15 temas/REsp = 29 entradas únicas, alinhado com o que o ingestor já
detectava antes de D.1) continuam íntegros — apenas metadata de verificação mudou.

## Tarefa humana entregue

`_workspace/13_human_curation_task_v1.3.md` contém:
- 3 URLs canônicas SCON (Cloudflare-gated) para 477, 532, 632.
- Ementa esperada em cada caso.
- DJe de cada súmula.
- Diff JSONL pronto para colar.
- Instruções de salvar HTML manualmente + hash + caminho de destino em
  `data/seed/case_law/_source/cloudflare_unblock/manual_{N}.html`.

## Ownership respeitado

Mudanças apenas em:
- `data/seed/case_law/stj_consumer_seed.jsonl` (já owned por ingestion)
- `data/seed/case_law/_source/cloudflare_unblock/` (vendoring)
- `data/seed/case_law/_source/MANIFEST.txt` (append)
- `_workspace/13_stj_cloudflare_unblock_summary.md` + `_workspace/13_human_curation_task_v1.3.md`

`packages/*` não tocado (preservado para D.2/D.3/D.4).
