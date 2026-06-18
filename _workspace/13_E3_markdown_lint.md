# E.3 — Correção de markdown lint (MD022 / MD040)

Escopo: corrigir APENAS MD022 (blank lines around headings) e MD040 (fenced code blocks
sem linguagem). Nenhuma outra regra habilitada ou "consertada" (MD013, MD032, MD060, etc.
permanecem como estavam). Sem edição de código/Makefile/pyproject. Sem commit. Sem resolução
de threads no GitHub.

## Antes / depois (markdownlint-cli2 sobre `_workspace/**/*.md docs/**/*.md README.md`)

| Regra | Antes | Depois |
|---|---|---|
| MD022 | 122 (STATE) + 49 (CONTRACTS) + demais ≈ 271 | 0 |
| MD040 | 64 fences sem linguagem | 0 |

Total MD022/MD040 antes: 335 ocorrências. Depois: 0.
Demais regras não foram alteradas (MD013/MD060/MD032/... seguem inalteradas).

## MD040 — linguagem atribuída ao info-string (por conteúdo real do bloco)

Heurística: `json` para blocos iniciados por `{`/`[` que são JSON; `bash` para comandos
(`make`, `python`, `pytest`, `$ ...`); `text` para saída/diagramas genéricos. Duas detecções
automáticas foram corrigidas a mão por serem SAÍDA (não comando/JSON):

- `_workspace/06_retrieval_caselaw_summary.md:52` → era detectado `json`, corrigido para `text`
  (bloco `[OK] statute query=...` é saída de CLI, não JSON).
- `_workspace/06_answer_caselaw_summary.md:81` → era detectado `bash`, corrigido para `text`
  (bloco `make test -> ...` é saída, não comando executável).

Mapa de fences corrigidos (arquivo:linha → linguagem):

- README.md:19 → text ; README.md:48 → text
- docs/architecture.md:7,13,72 → text
- docs/evaluation.md:53 → text
- docs/legal-rag-design.md:7,31,39 → text ; :69,75 → json
- _workspace/01_foundation_summary.md:25,31 → text
- _workspace/02_ingestion_summary.md:46,55,62 → text ; :68 → bash
- _workspace/02_legal-domain_summary.md:28,36 → bash
- _workspace/04_answer_summary.md:20 → text
- _workspace/05_answer_auditor_summary.md:54 → text
- _workspace/06_answer_caselaw_summary.md:70 → text ; :81 → text (corrigido de bash)
- _workspace/06_retrieval_caselaw_summary.md:52 → text (corrigido de json) ; :80 → bash
- _workspace/07_agentic_summary.md:39,79 → text
- _workspace/11_answer_http_graph_summary.md:78,155 → bash ; :95,127 → text
- _workspace/13_answer_auditor_recalibration_summary.md:21,35,60,67,159 → text ; :113 → bash
- _workspace/13_eval_golden_expansion_summary.md:75 → text
- _workspace/13_eval_real_harness_summary.md:46 → text ; :93,104 → bash
- _workspace/13_eval_real_local_summary.md:48 → bash
- _workspace/13_ingestion_caselaw_expansion_summary.md:56 → bash ; :79 → text
- _workspace/13_ingestion_stj_curadoria_summary.md:86 → bash ; :100 → text
- _workspace/13_retrieval_recall_fix_summary.md:72 → text
- _workspace/13_review_fixes_ingestion_summary.md:38 → text
- _workspace/13_stj_cloudflare_unblock_summary.md:39 → text ; :70 → bash

(As linhas referem-se à numeração ORIGINAL; após inserir blank lines de MD022 nos mesmos
arquivos, os números deslocam.)

## Fences órfãos (unbalanced) removidos

Dois arquivos tinham um ``` final solto (fence sem abertura correspondente, pré-existente no
HEAD), que o markdownlint interpretava como fence de abertura sem linguagem (MD040). Como
adicionar linguagem transformaria prosa em bloco de código (mudança semântica indevida), o
fix correto e mínimo foi remover o delimitador órfão:

- `_workspace/09_ui_summary.md` — removida ``` final solta após a lista "## Saída lint/test".
- `_workspace/07_agentic_summary.md` — removida ``` final solta no fim do arquivo (envolvia
  headings/prosa das seções de validação/pendências).

## MD022 — blank lines around headings

Inseridas linhas em branco acima/abaixo de headings ATX (`#`..`######`) fora de blocos de
código. Maiores incidências:

- `_workspace/STATE.md` — 122 ocorrências corrigidas.
- `_workspace/CONTRACTS.md` — 49 ocorrências.
- `_workspace/10_answer_ad1_fix.md` — 10.
- `_workspace/08_eval_summary.md`, `09_ui_summary.md`, `10_foundation_summary.md`,
  `10_ui-docs_summary.md` — 6 cada.
- `_workspace/11_answer_offline_summary.md` — 7.
- `_workspace/01_foundation_summary.md` — 6 ; `11_answer_http_graph_summary.md` — 4.
- `_workspace/02_ingestion_summary.md`, `13_ingestion_caselaw_expansion_summary.md` — 3 cada.
- `_workspace/02_legal-domain_summary.md` — 2 ; `10_qa_final_report.md` — 1.

## Verificação

`npx markdownlint-cli2 "_workspace/**/*.md" "docs/**/*.md" "README.md" | grep -cE "MD022|MD040"`
→ **0**. Demais regras inalteradas.
