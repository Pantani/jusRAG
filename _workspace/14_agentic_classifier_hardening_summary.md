# Fase 14 — Endurecimento da taxonomia do classify_area (dono: agentic)

Fecha a categoria B + inventário do `14_qa_multiarea_report.md` / `14_answer_scope_rework_summary.md §4-5`:
o `classify_area` mis-classificava 7 casos, causando vazamento de OOS (answer recusa por área) ou
`unknown` indevido. Corrigido por PRINCÍPIO de regime-sem-corpus, não memorizando enunciados.
Offline/determinístico. Ownership: só `packages/agents/`.

## 1. O que mudou na taxonomia / ponderação

Antes: `classify_area` somava pesos por área (`_AREA_KEYWORDS`) e `max` decidia; empate caía no
primeiro do dict; `administrative` era só mais uma área no mapa de pesos. Problema: keywords
incidentais de áreas in-scope (`contrato`, `contribuição`) venciam ou empatavam com sinais de
regime fora-do-corpus, e termos OOS próprios não tinham precedência.

Mudanças:

1. **Novo `_OUT_OF_SCOPE_TERMS: dict[str, LegalArea]` com PRECEDÊNCIA ABSOLUTA.** `classify_area`
   agora checa esse mapa ANTES do scoring ponderado. Um termo próprio de regime sem corpus vence
   qualquer keyword incidental in-scope. Valor do mapa = área resolvida: `administrative` (existe no
   enum) ou `unknown` (todos os demais regimes sem corpus → recusa §2.2). Termos: administrativo
   (licitação, servidor público, concurso público, improbidade, ato administrativo), previdenciário
   (previdência, INSS, aposentadoria, benefício previdenciário, previdenciár), empresarial/societário
   (sociedade empresária/limitada/anônima, falência, recuperação judicial), propriedade industrial
   (registro de marca, marca registrada, patente de invenção, INPI, propriedade industrial),
   ambiental, eleitoral, internacional/migratório (naturalização, extradição), marítimo.
2. **`administrative` removido de `_AREA_KEYWORDS`** — migrou para `_OUT_OF_SCOPE_TERMS` com
   precedência (antes empatava 2×2 com civil em "licitação e contratos" e perdia por ordem do dict).
3. **`contribuição`/`contribuicao` removidos de TAX** — termo não-discriminante; previdenciário o usa.
   "contribuição" sozinha não mapeia tributário; previdência/INSS/aposentadoria → unknown.
4. **Vocabulário de sucessões/inventário adicionado a CIVIL** (peso 2): inventário, partilha, espólio,
   sucessão (herança já existia). Inventário judicial → CIVIL (CC sucessões / CPC procedimento).
5. **Anti-falso-positivo:** "marca"/"patente" isolados NÃO entram (genéricos demais — pergunta de
   consumo cita marca de produto). Só formas discriminantes: "registro de marca", "marca registrada",
   "patente de invenção". `_out_of_scope_match` extraída como helper (CC trivial; sem estouro C90).

Princípio geral aplicado: **termo próprio de um regime jurídico ausente do corpus → out-of-scope**,
prevalecendo sobre keyword incidental de área in-scope. Na dúvida, prefere recusa a vazar (§2.2).

## 2. Os 7 casos — antes / depois

| pergunta | antes | depois | esperado |
|---|---|---|---|
| licitação e contratos administrativos | civil (IN, vaza) | **administrative (OUT)** | OUT ✓ |
| servidor público / concurso | administrative | **administrative (OUT)** | OUT ✓ |
| aposentadoria por tempo de contribuição | tax (IN, vaza) | **unknown (OUT)** | OUT ✓ |
| INSS / previdência | tax (IN, vaza) | **unknown (OUT)** | OUT ✓ |
| sociedade empresária limitada | unknown* | **unknown (OUT)** | OUT ✓ |
| dissolução de sociedade anônima | (constitutional via "sociedade"†) | **unknown (OUT)** | OUT ✓ |
| inventário judicial de bens | unknown (IN indevido recusa) | **civil (IN)** | IN ✓ |

\* "sociedade empresária limitada" já dava unknown no estado atual; tornado explícito por princípio
(regime empresarial sem corpus). † O relatório de QA reportava "sociedade"→constitutional; no código
auditado nenhuma keyword constitutional casava "sociedade" — provável formulação distinta. De
qualquer modo, o regime empresarial agora tem sinal OOS próprio e não depende do scoring.

## 3. Matriz held-out (perguntas NOVAS, fora dos 7 e do golden)

OOS de regimes sem corpus (esperado out-of-scope):

| pergunta | obtido |
|---|---|
| registro de marca no INPI | unknown (OUT) ✓ |
| validade de uma patente de invenção | unknown (OUT) ✓ |
| licenciamento ambiental de uma usina | unknown (OUT) ✓ |
| propaganda eleitoral antecipada e candidatura | unknown (OUT) ✓ |
| extradição de estrangeiro foragido | unknown (OUT) ✓ |
| naturalização de estrangeiro residente | unknown (OUT) ✓ |
| transporte marítimo de cargas | unknown (OUT) ✓ |
| recuperação judicial de empresa | unknown (OUT) ✓ |
| improbidade administrativa de prefeito | administrative (OUT) ✓ |

In-scope variadas (esperado área certa):

| pergunta | esperado | obtido |
|---|---|---|
| usucapião extraordinária de imóvel | civil | civil ✓ |
| partilha de bens na herança | civil | civil ✓ |
| petição inicial e citação no processo civil | civil | civil ✓ |
| homicídio qualificado e pena | criminal | criminal ✓ |
| aviso prévio na rescisão do contrato de trabalho | labor | labor ✓ |
| fato gerador do ICMS | tax | tax ✓ |
| mandado de segurança contra ato ilegal | constitutional | constitutional ✓ |
| vício do produto e direito do consumidor | consumer | consumer ✓ |
| consumidor pode trocar produto de outra marca | consumer | consumer ✓ (sem falso-OOS) |

Generalização confirmada: regimes sem corpus não-vistos recusam; in-scope cai na área certa.

## 4. Caso ainda ambíguo (honesto)

- **"marca"/"patente" como substring:** mantive só formas discriminantes para não recusar perguntas
  de consumo que citam marca de produto. Trade-off: "registro de marca XYZ" de natureza consumerista
  (raríssimo) classificaria OOS. Aceitável por §2.2 (prefere recusa a vazar), e o caso comum de
  consumo ("trocar produto de outra marca") foi protegido e testado.
- **`unknown` no roteamento:** áreas OOS→`unknown` confiam no §14 (retrieval vazio/sem filtro →
  recusa). O answer-gate (`is_in_scope`) já recusa `unknown`/`administrative` direto, então o
  vazamento da categoria B está fechado na origem.

## 5. Lint / typing / testes (real)

- `ruff check packages/agents/classify_area.py tests/unit/agents/test_classify_area.py` → **All checks passed!**
- `ruff check packages/agents/classify_area.py --select C90` → sem violações (helper extraído).
- `mypy packages/agents/classify_area.py` → **Success: no issues found in 1 source file**.
- `pytest tests/unit/agents/test_classify_area.py` → **32 passed**.
- `pytest tests/unit/agents/` (graph + researcher_filters incluídos) → **44 passed**.

Testes adicionados em `tests/unit/agents/test_classify_area.py`:
`test_out_of_scope_regime_term_prevails_over_incidental_in_scope_keyword`,
`test_inventario_is_civil_in_scope`, `test_held_out_corpusless_regimes_are_out_of_scope` (8 params),
`test_generic_brand_term_does_not_leak_consumer_to_out_of_scope`.

## 6. Arquivos tocados (ownership agentic)

- `packages/agents/classify_area.py`: novo `_OUT_OF_SCOPE_TERMS` + `_out_of_scope_match` helper;
  `classify_area` checa OOS-próprio antes do scoring; `administrative` removido de `_AREA_KEYWORDS`;
  `contribuição` removida de TAX; sucessões/inventário adicionados a CIVIL.
- `tests/unit/agents/test_classify_area.py`: 4 grupos de teste novos (7 casos + held-out + anti-overfit).
