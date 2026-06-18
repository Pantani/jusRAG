# Fase 14 — Rework do gate de scope do AnswerWriter (dono: answer)

Fecha o P0 da QA (`_workspace/14_qa_multiarea_report.md`): o gate `_is_out_of_scope` por
lista fechada de strings (`_OOS_KEYWORDS`) estava overfit ao golden e quebrava nos dois
sentidos. Offline/determinístico (fake providers, sem rede). NÃO toquei `tests/evals/`,
`packages/evals/`, `packages/agents/` nem `data/seed/questions/`.

## 1. O que substituiu a lista de strings

`_OOS_KEYWORDS` (tuple de ~70 strings) e o `_OOS_REGEX` foram **removidos**. O gate agora é
um sinal principled de **classe-de-área + ausência de corpus**, reusando a função pura e
determinística do agentic:

```python
from packages.agents.classify_area import classify_area, is_in_scope

def _is_out_of_scope(question: str) -> bool:
    return not is_in_scope(classify_area(question))
```

- Área classificada FORA de `IN_SCOPE_AREAS` (administrative/unknown) → regime sem corpus →
  recusa segura (§2.2), antes da chamada ao LLM.
- Área in-scope → NÃO recusa por keyword; o grounding fica com `_grounded` (limiar 0.29,
  inalterado) + CitationAuditor (§31). Se o retrieval não traz base, recusa por ausência de
  base, não por string.

Importar `classify_area` não é editar o agentic (função pura/importável, taxonomia geral,
não ajustada ao golden). NÃO dupliquei a lista de keywords do classificador. Dependência
documentada em `CONTRACTS.md` (answer → agentic), broadcast às outras sessões.

`_MIN_SEMANTIC_SCORE` mantido em 0.29. Comentários reescritos para refletir que a separação
de OOS passa a ser por classe-de-área, não por limiar absoluto.

## 2. Os 10 testes da QA — antes/depois

In-scope (devem responder) e OOS fora-do-golden (devem recusar), reproduzidos via
`build_harness()` (corpus real de 6329 chunks, fake embedding/LLM):

| caso | antes | depois |
|------|-------|--------|
| usucapião extraordinária (CC) | refused (errado) | **answered** ✓ |
| aviso prévio do empregado CLT | refused (errado) | **answered** ✓ |
| divórcio (hipóteses) | refused (errado) | **answered** ✓ |
| ICMS / fato gerador no CTN | refused (errado) | **answered** ✓ |
| furto — pena de reclusão (golden criminal) | refused (errado) | **answered** ✓ |
| homicídio simples (golden criminal) | refused (errado) | **answered** ✓ |
| inventário judicial de bens (CPC) | refused | **refused** ✗ (ver §5) |
| marca/INPI (OOS) | answered (vaza) | **refused** ✓ |
| licenciamento ambiental (OOS) | answered (vaza) | **refused** ✓ |
| naturalização de estrangeiro (OOS) | answered (vaza) | **refused** ✓ |
| LGPD (OOS) | answered (vaza) | **refused** ✓ |

OOS fora-do-golden: **5/5 recusam** (antes 1/5). In-scope com corpus: **6/7 respondem**
(antes 0/6). Os 2 falsos negativos criminais do próprio golden foram corrigidos.

## 3. Os 4 números do gate §36 (fake, offline, EVAL_GATE_STRICT)

| métrica | threshold | valor | resultado |
|---------|----------:|------:|-----------|
| retrieval_recall_at_5 | ≥ 0.80 | **0.9375** | PASS (inalterado) |
| citation_coverage | ≥ 0.90 | **1.0000** | PASS |
| unsupported_legal_claim_rate | ≤ 0.05 | **0.0000** | PASS |
| refusal_when_no_source_rate | ≥ 0.90 | **0.5000** | **FAIL** (ver §4) |

Recall@5 por área inalterado: civil/criminal/labor/tax/constitutional = 1.0; consumer =
0.9098 (misses `cdc-*` pré-existentes). §2.2 inviolável: nenhuma resposta com fonte
inventada; recusas saem com `sources: []`.

## 4. Por que refusal=0.50 e por que NÃO maquiei

O gate mede refusal sobre os 40 itens do `out_of_scope_golden.yaml`. Decompondo os 20
"answered":

- **Categoria A — 14 itens são in-scope reais com corpus** (golden stale, escrito para o gate
  de keywords antigo): usucapião, divórcio/família, ICMS/IRPF/ITCMD-tax, CLT, latrocínio,
  homicídio-STF. AGORA têm corpus (CC/CPC/CTN/CLT/CP ingeridos) → **responder é o
  comportamento correto** pelo novo design. São exatamente os casos que a QA listou como
  falsos-negativos a corrigir. O eval-agent deve migrá-los de OOS p/ in-scope (os 3 testes
  vermelhos refletem isso). Refusal honesto sobre OOS reais (26 itens) = **20/26 = 0.769**.

- **Categoria B — 6 itens são OOS reais que o classificador do agentic mal-classifica para
  área in-scope** por tokens compartilhados: "licitação... contratos" → `civil` (via
  `contrato`/`citação`); "aposentadoria por tempo de contribuição" → `tax` (via
  `contribuição`); "sociedade" → `constitutional`. Por design, área in-scope difere ao
  grounding, e o FakeEmbedding léxico dá score 0.32–0.41 contra chunks tangenciais → vazam.

Fechar 0.90 exigiria (a) reintroduzir keywords no answer — o bug que a QA reprovou, recriando
os falsos-negativos in-scope; ou (b) corrigir a ponderação discriminante do classificador no
agentic (peso de `licitação`/`servidor` vencer `contrato`; remover `contribuição` de tax ou
torná-lo desempate) — **fora do meu ownership**. Não fiz nenhuma das duas. Limiar absoluto
não separa (QA já provou; filtrar por área baixa licitação só a 0.323, ainda > 0.29).

## 5. Honestidade sobre fragilidade

- **inventário judicial (in-scope, frágil):** "Como se processa o inventário judicial de
  bens?" classifica como `unknown` (o classificador não tem stem `inventário`/`bens`) →
  recusa. É falso-negativo, mas a causa é cobertura do classificador (agentic), não o gate.
  Adicionar keyword no answer recriaria o overfit; o fix correto é no `_AREA_KEYWORDS`.
- **Categoria B acima:** 6 OOS reais vazam por mis-classificação do agentic. Generaliza para
  OOS não-vistas cuja área é corretamente classificada como administrative/unknown (marca,
  ambiental, LGPD, naturalização — todas recusam); falha apenas quando o classificador erra a
  área. Esse é o teto principled: o answer confia no classificador e não re-codifica keywords.

Recomendação ao orquestrador: (1) eval-agent migra os 14 itens da categoria A de OOS para
in-scope nos golden e religa os 3 testes vermelhos; (2) agentic endurece a ponderação do
`classify_area` para os 6+1 casos da categoria B e inventário. Só então o gate §36 fecha
honestamente — sem reintroduzir o overfit no answer.

## 6. Lint / mypy / testes (resultado real)

- `ruff check packages/answer packages/llm` → **All checks passed!** (C90 ≤ 10; o gate é
  uma expressão booleana, CC trivial).
- `mypy packages/answer packages/llm` → **Success: no issues found in 12 source files**.
- `pytest tests/unit/answer/ tests/evals/test_unsupported_claims.py tests/integration/test_ask.py`
  → **40 passed**.
- `make ask-demo` → consumer responde com legislação + Súmulas STJ 297/479 + Tema 1061
  (coverage 1.00, unsupported 0.00); "alíquota de IR sobre criptomoedas" → `refused`,
  `sources: []`.

## 7. Arquivos tocados (ownership answer)

- `packages/answer/answer_writer.py`: removidos `_OOS_KEYWORDS`/`_OOS_REGEX`/`import re`;
  `_is_out_of_scope` reescrito sobre `classify_area`/`is_in_scope`; comentários do gate e do
  `_MIN_SEMANTIC_SCORE` reescritos.
- `CONTRACTS.md`: criado — documenta a dependência answer → agentic (classificador de área) e
  a limitação conhecida de mis-classificação (categoria B).
