# Fase C — Multi-area scope classifier (packages/agents/classify_area.py)

## Problema (STATE sessão 9)
`classify_area` retornava UNKNOWN para áreas sem keywords; researchers aplicavam
`legal_area="unknown"` como filtro no Qdrant, zerando o retrieval. Com corpus multi-área
(CF/CC/CPC/CP/CPP/CLT/CTN + CDC) o risco volta para civil/penal/trabalhista/tributário.

## Mudanças

### 1. `_AREA_KEYWORDS` — vocabulário ponderado e discriminante
Estrutura passou de `tuple[str,...]` para `dict[str,int]` (peso). Termos próprios de um
único código pontuam **2**; termos compartilhados/ambíguos pontuam **1** (só desempatam).
`_score_area` agora soma pesos. Substring match cobre flexões (`tributár`, `empregad`).

- **consumer** (inalterado em cobertura, agora ponderado): consumidor/fornecedor/cdc (2),
  vício do produto, instituição financeira, conta corrente (2); produto/serviço/compra/
  defeito/garantia/troca/reembolso/banco/cartão/fraude (1).
- **civil (CC+CPC)**: usucapião, responsabilidade civil, dano moral, herança, casamento,
  divórcio, condomínio, locação, posse, petição inicial, tutela (2); contrato, propriedade,
  obrigação, prescrição, indenização, recurso, citação, sentença, execução (1).
- **criminal (CP+CPP)**: homicídio, furto, roubo, estelionato, legítima defesa, dolo,
  inquérito, habeas corpus, flagrante, denúncia (2); crime, pena, penal, delito, culpa,
  prisão (1).
- **labor (CLT)**: clt, empregad(or), trabalhador, fgts, hora extra, aviso prévio,
  rescisão, jornada (2); férias, salário, demiss, trabalh (1).
- **tax (CTN)**: icms, iss, ipi, fato gerador, crédito/obrigação tributária, lançamento,
  tributár, tributo (2); imposto, taxa, contribuição, fiscal, cripto (1).
- **constitutional (CF)**: direito fundamental, garantia constitucional, mandado de
  segurança, devido processo, separação de poderes, competência da união (2);
  constitucional/constituição (1).
- **administrative** (OUT, sem corpus): licitação, servidor público, concurso público,
  improbidade (2) — classifica honestamente mas fica fora de escopo.

**Sobreposições tratadas por discriminância:**
- "contrato" é peso-1 civil; "contrato de compra de produto com o fornecedor" → CONSUMER
  (consumidor/produto/fornecedor superam). "contrato de locação e posse" → CIVIL.
- "prescrição" peso-1 civil; vence consumer só com cues de consumo
  ("prescrição da garantia do produto do fornecedor" → CONSUMER).
- "habeas corpus" só existe em CRIMINAL (2) → desempata sem poluir civil.

### 2. IN_SCOPE generalizado
`IN_SCOPE_AREA = CONSUMER` (singular) → `IN_SCOPE_AREAS: frozenset` =
{consumer, civil, criminal, labor, tax, constitutional}. `is_in_scope` testa pertinência
ao conjunto. **administrative** e **unknown** permanecem OUT.

### 3. Recusa segura (§2.2) preservada — não relaxada
O gate de recusa no grafo (`_route_after_select`) depende **exclusivamente** de
`selected_context` vazio, não de `is_in_scope`. `is_in_scope` controla apenas o *caveat*
de cobertura. Logo, tornar 6 áreas in-scope não abre brecha: administrative/tema-sem-fonte
continuam recusando quando o retrieval volta vazio. O nó classify nunca redige resposta
(teste garante ausência de draft/final_answer no update).

### 4. Interação com researchers (fix sessão 9 mantido)
statute/case_law researchers seguem pulando o filtro `legal_area` quando
`legal_area in {None, "unknown"}` e aplicando-o quando a área é conhecida. Com a
classificação melhorada, as 6 áreas conhecidas filtram corretamente (corpora disjuntos);
UNKNOWN continua não-filtrando (não zera retrieval). Testado por spy de SearchService.

## Testes (offline, determinísticos)
- `tests/unit/agents/test_classify_area.py` (novo): 14 casos parametrizados das 6 áreas
  in-scope, overlaps contrato/prescrição, administrative OUT, unknown sem evidência,
  conjunto IN_SCOPE_AREAS, caveat só fora de escopo, nó não inventa resposta.
- `tests/unit/agents/test_researcher_filters.py` (novo): filtro aplicado p/ área conhecida,
  pulado p/ unknown, em statute e case_law.
- `tests/unit/agents/test_graph.py`: ajustado o nó-test (TAX agora in-scope → sem caveat;
  administrative → caveat "fora da cobertura").

## Resultado real
- `pytest tests/unit/agents/` → **33 passed**.
- `ruff check` (incl. `--select C901`) → All checks passed (CC<=10 ok).
- `mypy packages/agents` (strict) → Success: no issues found in 14 source files.

## Ownership
Alterado apenas `packages/agents/classify_area.py` e testes em `tests/unit/agents/`.
Nenhuma fonte inventada; §2.2 intacta.
