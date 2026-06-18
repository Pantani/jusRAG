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

## SHA256

Veja `MANIFEST.txt` (gerado por `shasum -a 256 *`).
