# 14 — legal-domain: aperto da regra de autoridade (`tier_for_statute`)

PR #3 / CodeRabbit. Ownership: `packages/legal_types/` + `tests/unit/legal_types/`.

## Bug

Fallback permissivo em `tier_for_statute` (hierarchy.py ~85-89): após `_FEDERAL_LAW_NORMS`,
um `if norm: return FEDERAL_LAW` fazia QUALQUER `norm_type` não-vazio (incl. typo/infralegal
como `portaria`, `decreto`) receber autoridade federal 0.95 — inflando autoridade e tornando
`_FEDERAL_LAW_NORMS` decorativo (não-autoritativo).

## Diff conceitual

Antes: `norm ∈ _FEDERAL_LAW_NORMS → FEDERAL_LAW` · `norm não-vazio → FEDERAL_LAW` · `vazio → UNKNOWN`.
Depois (estrito): `norm == constituicao → CONSTITUTION (1.00)` · `norm ∈ _FEDERAL_LAW_NORMS → FEDERAL_LAW (0.95)` ·
**qualquer outro valor (não-vazio OU vazio) → UNKNOWN (0.10)**. Removido o `if norm: return FEDERAL_LAW`.

Whitelist inalterada: `{lei, lei_complementar, decreto_lei, medida_provisoria}`. Todos os
norm_type reais do corpus seguem mapeando: constituicao→1.00; lei/lei_complementar/decreto_lei/
medida_provisoria→0.95. Só desconhecidos perdem o 0.95.

## Testes

Novo `test_unknown_norm_type_does_not_inflate_to_federal_law` (asserção negativa):
- `tier_for_statute("portaria") is UNKNOWN`; peso == 0.10 e != 0.95.
- `tier_for_statute("decreto") is UNKNOWN` (decreto regulamentar infralegal).
Casos positivos mantidos: `test_decreto_lei_maps_to_federal_law` (0.95), CF→1.00, lei→0.95, None→UNKNOWN.

## Lint / test (real)

- `./.venv/bin/python -m pytest tests/unit/legal_types/ -q` → 33 passed.
- `ruff check` (hierarchy.py + test) → No issues found (C90<=10 ok).
- `mypy packages/legal_types/hierarchy.py` (strict) → Success: no issues found.

## Paridade / consumidores a revalidar

`packages/rag/legal_ranker.py` (ownership retrieval) tinha lógica espelhada permissiva
("norm não-vazio ≠ constituição → FEDERAL_LAW"). NÃO editado aqui. Orquestrador deve aplicar a
MESMA whitelist estrita lá. CONTRACTS.md (linhas ~67-69) corrigido de "demais norm não-vazios →
FEDERAL_LAW" para a regra estrita autoritativa.
