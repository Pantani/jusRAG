# STJ Source Vendoring Manifest

Origem dos arquivos auditáveis usados para promover entradas em `stj_consumer_seed.jsonl` de
`needs_review` para `verified` em 2026-06-18.

Fonte primária: portais oficiais STJ.

## Súmulas (PDF — Revista de Súmulas, biblioteca digital STJ)

| Arquivo | Súmula | URL oficial |
|---------|--------|-------------|
| stj_sumula_359.pdf | 359 | https://www.stj.jus.br/docs_internet/revista/eletronica/stj-revista-sumulas-2012_31_capSumula359.pdf |
| stj_sumula_381.pdf | 381 (substituta, ver abaixo) | https://www.stj.jus.br/docs_internet/revista/eletronica/stj-revista-sumulas-2013_34_capSumula381.pdf |
| stj_sumula_385.pdf | 385 | https://www.stj.jus.br/docs_internet/revista/eletronica/stj-revista-sumulas-2013_35_capSumula385.pdf |
| stj_sumula_404.pdf | 404 | https://www.stj.jus.br/docs_internet/revista/eletronica/stj-revista-sumulas-2014_38_capSumula404.pdf |

### Súmula REMOVIDA do seed v1.1

| Súmula | Razão |
|--------|-------|
| 321 | PDF da Revista de Súmulas (2011_26) baixado e verificado: enunciado vem com flag "(Cancelada)". A Súmula 321 foi cancelada pela Súmula 563/STJ. Substituída pela Súmula 381 (consumer/bancário válida) no seed. |

## Temas Repetitivos (HTML — Banco de Precedentes Qualificados STJ)

Endpoint: `POST https://processo.stj.jus.br/repetitivos/temas_repetitivos/pesquisa.jsp`
Form body: `p=true&novaConsulta=true&quantidadeResultadosPorPagina=10&i=1&pesquisa_livre=&operadorPadrao=e&tipo_pesquisa=T&cod_tema_inicial=<N>&cod_tema_final=<N>`

| Arquivo | Tema | Categoria |
|---------|------|-----------|
| stj_tema_27.html  | 27   | substituto (consumer/bancário) |
| stj_tema_35.html  | 35   | substituto (consumer/cadastros) |
| stj_tema_247.html | 247  | substituto (consumer/capitalização juros) |
| stj_tema_575.html | 575  | substituto (consumer/serviço público — rede elétrica) |
| stj_tema_577.html | 577  | substituto (CDC/incorporação imobiliária) |
| stj_tema_610.html | 610  | substituto (CDC/plano de saúde — prescrição) |
| stj_tema_938.html | 938  | mantido do seed v1.1 (corretagem imóvel) |
| stj_tema_939.html | 939  | mantido (incorporadora — corretagem) |
| stj_tema_952.html | 952  | mantido (plano de saúde — faixa etária) |
| stj_tema_953.html | 953  | substituto (juros capitalizados mútuo) |
| stj_tema_958.html | 958  | mantido (contratos bancários — ressarcimento serviços) |
| stj_tema_960.html | 960  | mantido (corretagem MCMV) |
| stj_tema_990.html | 990  | mantido (plano de saúde — medicamento sem ANVISA) |
| stj_tema_1061.html| 1061 | substituto (CDC/ônus assinatura contrato bancário) |
| stj_tema_1112.html| 1112 | substituto (seguro de vida coletivo) |

## Temas REMOVIDOS do seed v1.1 (ementa do seed não correspondia à tese real do STJ)

| Tema | Seed v1.1 dizia | Realidade extraída do STJ |
|------|-----------------|---------------------------|
| 666  | exibição docs bancários | Telefonia PCT |
| 717  | purgação mora alienação fiduciária | MP em ação de alimentos |
| 887  | tarifas bancárias financiamento | Expurgos Plano Verão poupança |
| 932  | restituição parcelas promessa C&V | Prescrição repetição indébito água/esgoto |
| 950  | revisão cláusulas bancárias | Trade dress / concorrência desleal |
| 988  | acidente consumo arts. 12/14 CDC | Taxatividade mitigada art. 1.015 CPC |
| 1006 | tarifa registro contrato veículos | Unificação penas execução penal |
| 1020 | juros remuneratórios bancários | FGTS servidores LCE/MG |
| 1030 | capitalização juros pós-MP 2170-36 | Renúncia ao excedente JEF Cível |

Estas 9 entradas configuravam violação direta da regra §2 (NUNCA INVENTAR) e foram substituídas
por Temas reais de Direito do Consumidor (lista de substitutos acima).

## Súmulas com snapshots Wayback removidos (review #3435741430)

Em 2026-06-18 foi descoberto que os HTMLs em `cloudflare_unblock/wayback_*.html` (snapshots
Wayback Machine 2022-11-21 do SCON/STJ) na verdade vendoravam a página de challenge
JavaScript do Cloudflare/TSPD, sem nenhum conteúdo de Súmula. O snapshot capturado pelo
Wayback é o próprio HTML do interstitial — o JavaScript que renderiza a Súmula nunca foi
executado. Portanto:

- Diretório `cloudflare_unblock/` foi removido.
- Súmulas 472, 595 e 608 foram revertidas de `verified` para `needs_review` em
  `stj_consumer_seed.jsonl`.
- Súmulas 477, 532 e 632 permanecem `needs_review` (notas atualizadas para refletir a
  causa real — não havia conteúdo no snapshot vendored).

Reverificação dessas seis Súmulas requer browser real com solver de Cloudflare ou PDF da
Revista de Súmulas. Ver `_workspace/13_human_curation_task_v1.3.md`.

## Encoding dos HTMLs de Temas

Em 2026-06-18 os 15 arquivos `stj_tema_*.html` foram re-codificados de ISO-8859-1 (latin-1,
encoding nativo do SCON/STJ) para UTF-8, com atualização concomitante da declaração
`<meta charset>`. Conteúdo é byte-equivalente após decode; SHA256 mudaram (ver
`MANIFEST.txt`).

## SHA256

`MANIFEST.txt` é gerado deterministicamente por:

```sh
cd data/seed/case_law/_source
find . -type f \( -name '*.pdf' -o -name '*.html' \) -print0 \
  | LC_ALL=C sort -z \
  | xargs -0 shasum -a 256 > MANIFEST.txt
```

Validar integridade com `shasum -a 256 -c MANIFEST.txt` a partir de
`data/seed/case_law/_source/`.
