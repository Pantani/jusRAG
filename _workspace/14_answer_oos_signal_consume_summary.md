# 14 — answer consome o sinal OOS explícito do agentic (§2.2)

## Mudança
`packages/answer/answer_writer.py` — `_is_out_of_scope` agora usa o sinal determinístico
`matched_out_of_scope_regime` exposto pelo agentic
(_workspace/14_agentic_oos_signal_summary.md), resolvendo a tensão entre não pré-recusar
UNKNOWN sem-evidência e §2.2 (regimes corpusless vazando).

```python
from packages.agents.classify_area import (
    classify_area,
    is_in_scope,
    matched_out_of_scope_regime,
)

def _is_out_of_scope(question: str) -> bool:
    if matched_out_of_scope_regime(question):
        return True   # regime corpusless casado → pré-recusa §2.2 (independe de embedding)
    area = classify_area(question)
    if area is LegalArea.UNKNOWN:
        return False  # sem evidência → prossegue ao retrieval (fonte real pode surgir)
    return not is_in_scope(area)
```

Import adicionado; comentário do gate reescrito explicando o split sobre o sinal
explícito. Função permanece trivial (CC bem abaixo de 10), sem extração necessária.

## Comportamento (corrige os dois lados)
- "Como registrar marca no INPI?" → regime casado → **REFUSED** (corrige vazamento §2.2).
- "requisitos do licenciamento ambiental" → **REFUSED**.
- "aposentadoria ... INSS" (previdenciário) → **REFUSED**.
- administrative ("improbidade ...") → **REFUSED** (regime + área definida fora de escopo).
- "arrolamento dos bens deixados" (inventário, UNKNOWN sem-keyword) → **NÃO** pré-recusado
  → segue ao retrieval; responde se há base (corrige falso-negativo in-corpus).
- usucapião → classifica CIVIL → não pré-recusado.
- in-scope consumer/civil → responde.

## Testes (tests/unit/answer/test_answer_writer.py)
Novos: `test_inpi_trademark_regime_pre_refuses` / `_refuses_safely`,
`test_environmental_licensing_regime_pre_refuses` / `_refuses_safely`,
`test_social_security_regime_pre_refuses`, `test_in_scope_civil_usucapiao_is_not_pre_refused`.
Cobrem (a) INPI, (b) ambiental, (c) inventário/usucapião sem-evidência (não pré-recusado),
(d) administrative REFUSED, (e) in-scope responde. Os pré-existentes
(`test_administrative_*`, `test_unknown_no_evidence_*`, `test_in_scope_question_cites_art_12`)
seguem válidos sob a nova lógica.

## Lint/test reais
- `uv run pytest tests/unit/answer/` → **36 passed** (0.13s, offline, fake providers)
- `uv run ruff check packages/answer/answer_writer.py tests/unit/answer/test_answer_writer.py` → All checks passed
- `uv run ruff check --select C901 packages/answer/answer_writer.py` → All checks passed (CC<=10)
- `uv run mypy packages/answer/answer_writer.py` → Success, no issues (strict)

## Coordenação
Restaura a recusa determinística dos regimes corpusless. O eval pode devolver esses itens
ao golden OOS (coordenado pelo eval/agentic). Ownership respeitado: alterado apenas
packages/answer/ + tests/unit/answer/. Dependência de contrato: answer importa
`matched_out_of_scope_regime` do agentic — atualizar CONTRACTS.md com essa import adicional.
