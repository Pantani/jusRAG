# Fase 13.D.5 — review fixes (ingestion ownership)

PR #1 review comments endereçados pelo escopo `ingestion`. Total: 6 findings.

## Tabela de findings → ações

| # | Comment ID | File / Concern | Ação |
|---|------------|----------------|------|
| 1 | 3435741430 | `wayback_632.html`: snapshot vendored era página de challenge Cloudflare/TSPD, sem conteúdo da Súmula 632 | **Removido o arquivo.** Súmula 632 já estava `needs_review` no JSONL; nota de verificação reescrita para refletir a causa real (snapshot só continha challenge JS, não conteúdo). |
| 2 | (geral) | Mojibake/encoding em 15 `stj_tema_*.html` (latin-1 servido como UTF-8) | **Re-codificado** todos os 15 HTMLs de ISO-8859-1 → UTF-8 in-place, com `<meta charset>` atualizado. Validação: `find … -name '*.html' \| xargs grep $'\xef\xbf\xbd'` → 0 hits. Todos arquivos `file(1)`-detectados como `UTF-8 text`. |
| 3 | (geral) | `wayback_477.html` "0-result" no manifest, mas conteúdo divergia | **Removido** junto com `cloudflare_unblock/`. Era Cloudflare interstitial, não snapshot SCON real. JSONL já estava `needs_review`; nota atualizada. |
| 4 | 3435741446 | `MANIFEST.txt`: comentários inline (`# 0-result snapshot…`) quebravam `shasum -c` | **Regenerado** sem comentários inline. `shasum -a 256 -c MANIFEST.txt` agora PASSA limpo. |
| 5 | 3435741437 | `MANIFEST.md` documentava `shasum -a 256 *` (não-determinístico) | **Substituído** por `find . -type f \( -name '*.pdf' -o -name '*.html' \) -print0 \| LC_ALL=C sort -z \| xargs -0 shasum -a 256`. MANIFEST.txt regenerado com este comando. |
| 6 | 3435741406 | `ingest_cdc.py`: `regenerate_seed_from_html()` falso não abortava → chunks stale | **Fail fast**: `main()` agora retorna 1 e escreve mensagem em stderr quando o HTML do Planalto não existe. Novo teste `test_main_fails_fast_when_source_html_missing` cobre o exit 1. |

## Decisão chave: snapshots Wayback removidos em bloco

Investigando finding #1, descobri que **todos** os arquivos em `cloudflare_unblock/` eram a mesma
página de challenge JavaScript do Cloudflare/TSPD — sem nenhum conteúdo SCON real. O Wayback
Machine capturou o HTML do interstitial, mas o JS que renderiza a Súmula nunca foi executado, então
os arquivos vendored servem apenas como "evidência de que o Cloudflare bloqueou tudo".

Tratar isso como evidência válida violava §40.4 e §2 (audit-trail quebrado). Portanto:

- Diretório `data/seed/case_law/_source/cloudflare_unblock/` **removido** completamente (6 arquivos).
- Súmulas 472, 595, 608 **revertidas** de `verified` → `needs_review` em `stj_consumer_seed.jsonl`
  (entradas marcadas como `verified` em commit anterior apontavam para o mesmo lixo).
- Súmulas 477, 532, 632 permanecem `needs_review` mas notas reescritas para refletir que o
  snapshot vendored não continha dados (antes diziam "0 resultados na busca dinâmica", o que dava
  a entender que havia HTML real com 0 resultados — não havia HTML real).
- Reverificação dessas 6 Súmulas requer browser real com solver de Cloudflare ou PDF da Revista
  de Súmulas. Documentado em `_workspace/13_human_curation_task_v1.3.md`.

## Arquivos re-vendored (re-encoded) + novos SHA256

15 arquivos `stj_tema_*.html` (ISO-8859-1 → UTF-8). Novos SHA256:

```text
9fede2e74f10eaa41bc38de2429025a9978a00f9892956424903138b472226ee  stj_tema_1061.html
03702d7b65d1ab910122f282a610703c8e98bca06bd762492be3f187aa4849cf  stj_tema_1112.html
5de7e20d511234f745dae5d054a1d09cf67239bcc5cee2c217b64f41ebbe72bb  stj_tema_247.html
7f5682b48f0891b272ca7c507275c354880d3189ffe7e45ea3d1e98639e464b4  stj_tema_27.html
e08e3b8f7f0e6ce8a5afbe57107a2a7d5f6aa8560d2203fc0eae531fb64cedde  stj_tema_35.html
f58828b23e239f8cafbaa554d2c14702ea1d700e1b718d2ed2a9cd7ee24af804  stj_tema_575.html
5f7b9f5144b623d720a5cd754e5dcd91f2eee84d1cbf91b50229ae2be2e424a6  stj_tema_577.html
030a953103a04c3b3138ea763563df4184db87382eac81cade6f3a1460b98c69  stj_tema_610.html
d5fa3e1d12f1c3bd2d41b491cdeb55cb1a69974c14463e17e3c456690c770c8c  stj_tema_938.html
431a074bf76b16b1916fe08a2b1464018a599f2f9aa43828f915c09fe74c9335  stj_tema_939.html
ad5deddf3f3b760e441c27c1e85b546ee6e41dafc83d11e5bcfa628bbf434829  stj_tema_952.html
281c39577c07b3ceeacc500c8f174ed5b8cdc36e6236ed3c4f487f37367fe62a  stj_tema_953.html
2a3b375ba0b6f2cd9db159e3caf34d3890427fb8cf6d6f3a9c1d27a91d770361  stj_tema_958.html
ee057fd700cd39235349c0229352cd5af637895107c03e538cf05f293e61397c  stj_tema_960.html
5e2a682efba03f4977e1bfda3526b28b567f173c0726ec65fb60ae87011e39b9  stj_tema_990.html
```

PDFs das Súmulas (359, 381, 385, 404) **inalterados** — SHA256 idênticos.

Arquivos **removidos** (6, eram Cloudflare interstitials):

- `cloudflare_unblock/wayback_472.html`
- `cloudflare_unblock/wayback_477.html`
- `cloudflare_unblock/wayback_532.html`
- `cloudflare_unblock/wayback_595.html`
- `cloudflare_unblock/wayback_608.html`
- `cloudflare_unblock/wayback_632.html`

## Status Súmula 632

`needs_review` (downgrade já existia no JSONL). Nota de verificação reescrita para causa real:
snapshot Wayback vendored era apenas o HTML de challenge Cloudflare/TSPD, sem conteúdo. Arquivo
removido. Reverificação pendente de browser real com solver Cloudflare ou PDF Revista de Súmulas.

## Validação

| Check | Resultado |
|-------|-----------|
| `grep -RP "\xef\xbf\xbd" data/seed/case_law/_source/` (mojibake) | **0** hits |
| `shasum -a 256 -c data/seed/case_law/_source/MANIFEST.txt` | **OK** (19/19 arquivos) |
| `make test` | **203 passed** (35 ingestion incluindo novo `test_main_fails_fast_when_source_html_missing`) |
| `make lint` | **PASS** (ruff + mypy clean) |
| `python -m apps.worker.jobs.ingest_cdc` | **OK** — 130 chunks, arts. 1º–119, write `data/generated/cdc_chunks.jsonl` |
