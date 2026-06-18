# Tarefa humana — verificação manual de 3 súmulas STJ bloqueadas por Cloudflare

**Versão:** v1.3 (Fase 13.D.1)
**Data:** 2026-06-18
**Status:** 27/30 entradas STJ verificadas; **3 pendentes** (Súmulas 477, 532, 632).

## Por que precisa de você

Todos os endpoints automatizáveis do STJ que servem o texto oficial das súmulas estão atrás de
Cloudflare com JS challenge (`cf-mitigated: challenge`, HTTP 403) e exigem um browser real para
resolver:

| Endpoint | Resultado em 2026-06-18 |
|----------|-------------------------|
| `scon.stj.jus.br/SCON/sumstj/toc.jsp` (canônico) | HTTP 403 Cloudflare |
| `bdjur.stj.jus.br/jspui/simple-search` | HTTP 403 Cloudflare |
| `www.stj.jus.br/sites/portalp/...Noticias.aspx` | HTTP 403 Cloudflare |
| Wayback Machine (CDX) | Snapshots existem mas mostram 0 resultados (UI sem dados dinâmicos) para 477/532/632 |
| Revista de Súmulas PDFs (`docs_internet/.../capSumula{N}.pdf`) | Não publicado neste padrão p/ esses 3 (varredura 2010-2023 × 41 edições em C.1) |

**Para 472, 595 e 608** o snapshot Wayback de 2022-11-21 capturou o resultado da busca com sucesso
(enunciado literalmente presente) — promovidas a `verified` nesta tarefa.

## O que fazer

Abra cada URL abaixo no seu browser (Cloudflare passa em 1-2s) e **confira se o enunciado oficial
bate exatamente com o `ementa` que está no seed**. Se bater, edite
`data/seed/case_law/stj_consumer_seed.jsonl` trocando o bloco indicado.

### Súmula 477

- **URL oficial:** https://scon.stj.jus.br/SCON/sumstj/toc.jsp?livre=%27477%27.num.&O=JT
- **Ementa esperada (no seed):**
  > A decadência do artigo 26 do CDC não é aplicável à prestação de contas para obter
  > esclarecimentos sobre cobrança de taxas, tarifas e encargos bancários.
- **DJe:** 2012-06-19 (Segunda Seção)
- **Substituir no JSONL:**
  ```diff
  -  "verification_status": "needs_review",
  -  "verification_blocked": "cloudflare_scon",
  -  "verification_notes": "BLOQUEADO: SCON ... Ver _workspace/13_human_curation_task_v1.3.md ..."
  +  "verification_status": "verified",
  +  "verification_notes": "Verificado manualmente em <DATA> via browser na URL canônica SCON (Cloudflare-gated). Snapshot HTML salvo em data/seed/case_law/_source/cloudflare_unblock/manual_477.html (sha256 <HASH>)."
  ```
  Antes, salve o HTML como `data/seed/case_law/_source/cloudflare_unblock/manual_477.html`
  (Cmd+S → "Webpage, HTML Only") e rode `shasum -a 256 manual_477.html`.

### Súmula 532

- **URL oficial:** https://scon.stj.jus.br/SCON/sumstj/toc.jsp?livre=%27532%27.num.&O=JT
- **Ementa esperada (no seed):**
  > Em ação monitória fundada em cheque prescrito ajuizada contra o emitente, é dispensável a
  > menção ao negócio jurídico subjacente à emissão da cártula.
- **DJe:** 2015-06-15 (Corte Especial)
- **Substituir no JSONL:** mesmo padrão do 477 (`manual_532.html`).

### Súmula 632

- **URL oficial:** https://scon.stj.jus.br/SCON/sumstj/toc.jsp?livre=%27632%27.num.&O=JT
- **Ementa esperada (no seed):**
  > Nos contratos de seguro regidos pelo Código de Defesa do Consumidor, é cabível a inversão do
  > ônus da prova em favor do segurado.
- **DJe:** 2019-08-19 (Segunda Seção)
- **Substituir no JSONL:** mesmo padrão (`manual_632.html`).

## Verificação pós-edição

```bash
make ingest-case-law && shasum data/generated/case_law_chunks.jsonl
make lint
make eval
```

Após a verificação humana, atualize esta tabela em `_workspace/STATE.md`:
**30/30 STJ verified, 0 needs_review**.

## Garantia de não-invenção

O texto das 3 ementas no seed v1.2 foi originalmente coletado em C.1 a partir de fontes não-oficiais
(jurisprudência consolidada amplamente reproduzida). Não há divergência conhecida com o texto
oficial — esta tarefa é apenas a confirmação formal exigida pela regra §40.
