# Fase 14 — Remediação da dívida eval-real (dono: eval)

Reavalia os 9 itens de `out_of_scope_eval_real_debt.yaml` após o fix P1 de ingestão do CC
(separador de milhar). Ownership: `packages/evals/`-consumidor + `data/seed/questions/` +
`tests/evals/`. Offline/determinístico no caminho de CI; a medição do Grupo 2 usa o modelo
local sentence-transformers (sem rede, sem Ollama/LLM). NÃO toquei `answer_writer.py` nem
`classify_area.py`.

## 1. GRUPO 1 — promovidos a in-scope (o fix do CC os habilitou)

As 6 âncoras existem no corpus regenerado (`data/generated/statutes_chunks.jsonl`, 6169 chunks,
1 chunk cada — regra #1). Os 4 itens originais (`oos-usucapiao-imovel`, `oos-civ-01`, `oos-fam-01`,
`oos-fam-03`) foram retirados de `out_of_scope_eval_real_debt.yaml` e reescritos como 6 itens
`answered` em `civil_golden.yaml`, no esquema `civil-cc-*`, com a redação fiel ao texto real do
artigo (regra de calibração léxica do FakeEmbedding). Ids antigos aposentados (eram só dívida
documentada, nunca carregados pelo gate, então não há contrato de id a preservar).

| novo id | área | âncora (CC) | recuperado top-5 no fake? |
|---------|------|-------------|---------------------------|
| civil-cc-art1238-usucapiao-extraordinaria | civil | cc-10406-2002-art-1238 | S (pos 1) |
| civil-cc-art1242-usucapiao-ordinaria | civil | cc-10406-2002-art-1242 | S (pos 2) |
| civil-cc-art1658-comunhao-parcial | civil | cc-10406-2002-art-1658 | S (pos 1) |
| civil-cc-art1639-regime-bens | civil | cc-10406-2002-art-1639 | S (pos 1) |
| civil-cc-art1583-guarda-compartilhada | civil | cc-10406-2002-art-1583 | S (pos 1) |
| civil-cc-art1584-guarda-decretada | civil | cc-10406-2002-art-1584 | S (pos 1) |

Todas recuperadas em top-5 sob o FakeEmbedding léxico (verificado via `build_harness().search`).
As redações coloquiais originais davam MISS (a usucapião nem aparecia); a reescrita fiel ao texto
do artigo resolve sem forçar nada. `civil` passa de 12/12 para 18/18 no recall@5.

## 2. GRUPO 2 — medição com embeddings DENSOS reais (fecha a pergunta do débito)

5 itens tax mantidos em `out_of_scope_eval_real_debt.yaml`. Medição: indexei o corpus completo
(6329 chunks indexáveis) com `LocalEmbeddingProvider` (paraphrase-multilingual-mpnet-base-v2,
sentence-transformers 5.6.0, sem rede), rodei o retriever real (`search_separated`) e li o
`semantic_score` (cosseno bruto, idêntico ao sinal que `AnswerWriter._grounded` filtra) do top-1.
Limiar de grounding: `_MIN_SEMANTIC_SCORE = 0.29`.

| id | top-1 dense score | chunk top-1 | recusaria por grounding? | veredito |
|----|------------------:|-------------|--------------------------|----------|
| oos-declarar-bitcoin | 0.4962 | cp-2848-1940-art-289 | NÃO (0.50 ≫ 0.29) | débito REFUTADO |
| oos-tax-01 (IRPF) | 0.6438 | cf88-1988-1988-art-125-occ-2 | NÃO | débito REFUTADO |
| oos-tax-02 (ITCMD-SP) | 0.4799 | ctn-5172-1966-art-35 | NÃO | débito REFUTADO |
| oos-tax-03 (ICMS importação) | 0.6569 | ctn-5172-1966-art-20 | NÃO | débito REFUTADO |
| oos-tax-04 (subst. trib. ICMS) | 0.5699 | ctn-5172-1966-art-18-a | NÃO | débito REFUTADO |

**Veredito: o débito está REFUTADO, não é só artefato do fake.** O pressuposto antigo ("sob
embeddings reais a distância semântica é grande, então recusam") está ERRADO para este
threshold/modelo: os 5 itens pontuam 0.48–0.66, muito acima de 0.29, então o `_grounded` NÃO
recusaria — vazaria igual, ou pior, que no fake. A recusa correta destes itens NÃO depende do
grounding semântico denso; depende (a) da rota OOS do `classify_area` ou (b) do `CitationAuditor`
a nível de claim. Atualizei o cabeçalho do YAML para refletir o achado real (sem repetir a tese
antiga falsa) e mantive a pendência ao orquestrador como agentic, não retrieval.

Nota metodológica honesta: medi o sinal de grounding (semantic_score top-1), que é exatamente o
que decide recusa no `AnswerWriter`. Não rodei `make eval-real` completo (Ollama down + sem
credenciais OpenAI), mas para a pergunta "o grounding denso recusaria?" o score top-1 é o sinal
suficiente e o medi diretamente sobre o retriever real com o modelo local.

## 3. Gate §36 — `make eval` (fake/offline, EVAL_GATE_STRICT default)

`make eval` exige docker (target via compose); rodei o equivalente offline
`python -m packages.evals.run_all`. Golden carregado: **221** (in-scope 188, OOS 33).

| métrica | threshold | valor | resultado |
|---------|----------:|------:|-----------|
| retrieval_recall_at_5 | ≥ 0.80 | **0.9415** | PASS |
| citation_coverage | ≥ 0.90 | **1.0000** | PASS |
| unsupported_legal_claim_rate | ≤ 0.05 | **0.0000** | PASS |
| refusal_when_no_source_rate | ≥ 0.90 | **1.0000** | PASS |
| **Gate (strict) §36** | — | **PASSED** | — |

Recall@5 por área: civil **1.0 (18/18)**, constitutional 1.0 (10/10), consumer 0.9098 (111/122,
misses cdc-* pré-existentes), criminal 1.0 (13/13), labor 1.0 (15/15), tax 1.0 (10/10).
refusal=1.0 inalterado: os 33 OOS carregados continuam recusando; Grupo 1 saiu de um arquivo que
o gate nunca carregava e virou in-scope answered; Grupo 2 segue fora do gate. Sem maquiagem.

## 4. Testes atualizados

- `data/seed/questions/civil_golden.yaml`: +6 itens `civil-cc-*` (Grupo 1), comentário de
  procedência (promoção pós-fix do CC).
- `data/seed/questions/out_of_scope_eval_real_debt.yaml`: −4 itens (Grupo 1), cabeçalho reescrito
  com o achado dense real (débito refutado); 5 itens tax mantidos.
- `tests/evals/test_anti_overfit.py`: +2 casos positivos blind (usucapião CC-1238, guarda CC-1583)
  — exatamente os que migraram do débito, afirmados `status != refused`. Comentário do topo
  atualizado. `test_golden` (cardinalidades `>= 10`/`>= 5`) e `test_run_all` seguem por contrato
  tolerante — nenhum hard-coda os ids movidos, nada quebrou. §36/§2.2 NÃO relaxados.

## 5. Lint / mypy / testes (real)

- `ruff check tests/evals packages/evals --select C90` → **All checks passed!**
- `ruff check tests/evals packages/evals` → **All checks passed!**
- `mypy packages/evals` → **Success: no issues found in 8 source files**.
- `pytest tests/evals/` (junit) → **tests=55 failures=0 errors=0 skipped=0** (exit 0;
  era 53, +2 anti-overfit).
- `python -m packages.evals.run_all` (fake/offline strict) → **Gate (strict): PASSED**;
  relatório regenerado em `data/generated/eval_report.{json,md}`.

## 6. Pendência reportada ao orquestrador

Grupo 2 (5 itens tax): recusa NÃO pode vir do grounding denso (medido: 0.48–0.66 ≫ 0.29). Dono =
**agentic**: `classify_area` deve rotear sub-tópicos sem-corpus de uma área in-scope (alíquota IRPF,
ITCMD/ICMS estaduais — ausentes do CTN, que é norma geral) para OOS, OU o writer deve recusar com
base no `CitationAuditor` a nível de claim. NÃO é pendência de retrieval/ingestion.
