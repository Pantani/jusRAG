# 14 — Retrieval authority parity (legal_ranker ↔ hierarchy)

## Bug (CodeRabbit, PR #3)
`authority_for_payload` (packages/rag/legal_ranker.py) tratava QUALQUER `norm_type`
não-vazio ≠ constituição como `FEDERAL_LAW` (0.95). Logo um `norm_type` desconhecido
ou com typo (ex.: `"portaria"`, infralegal) recebia 0.95 indevidamente — divergindo de
`_FEDERAL_LAW_NORMS` e da intenção de `hierarchy.tier_for_statute`.

## Correção — espelho estrito reusando a constante de hierarchy
Não foi possível delegar diretamente a `hierarchy.tier_for_statute` porque essa função
recebe um `LegalChunk` (schema), não um payload `dict[str, object]`; construir um chunk só
para isso acoplaria o ranker à schema. Optei por **paridade estrutural mínima**: importei a
constante de verdade `_FEDERAL_LAW_NORMS` de `packages.legal_types.hierarchy` e apliquei a
MESMA regra:

- `norm_type in {"constituicao","constituição"}` → CONSTITUTION (1.00)
- `norm_type in _FEDERAL_LAW_NORMS` (`lei`, `lei_complementar`, `decreto_lei`,
  `medida_provisoria`) → FEDERAL_LAW (0.95)
- qualquer outro não-vazio / vazio / desconhecido → UNKNOWN (0.10)

Como o conjunto canônico vem de hierarchy, a lista de norm types federais não pode mais
divergir entre os dois módulos.

## Nota para o orquestrador (export em hierarchy)
Reusei `_FEDERAL_LAW_NORMS`, que hoje é **privado** (underscore) em hierarchy.py. Ruff/mypy
strict passam, mas o ideal de longo prazo é hierarchy expor algo público payload-friendly
para o ranker delegar 100% sem espelho nem import privado. Sugestões (ownership legal-domain,
NÃO toquei em hierarchy.py):
- promover `_FEDERAL_LAW_NORMS` → `FEDERAL_LAW_NORMS` (público); OU
- expor `tier_for_norm_type(norm_type: str) -> AuthorityTier` pública e fazer
  `authority_for_payload` delegar a ela (paridade total, sem espelho).
Se hierarchy expuser uma dessas, troco o import de 1 linha. Por ora a regra está espelhada e
verde.

## Teste de paridade adicionado
`tests/unit/rag/test_legal_ranker.py::test_unknown_norm_type_not_federal_law`:
- `norm_type="portaria"` → `authority_for_payload` != 0.95 e == 0.10 (UNKNOWN).
Mantidos: `decreto_lei` → 0.95, `constituicao` → 1.00, federal-law default → 0.95.

## Lint/test real (uv)
- `pytest tests/unit/rag/` → 28 passed.
- `ruff check packages/rag/` → All checks passed.
- `mypy packages/rag/legal_ranker.py tests/unit/rag/test_legal_ranker.py` → Success, no issues.

## Ownership
Editado apenas `packages/rag/legal_ranker.py` e `tests/unit/rag/test_legal_ranker.py`.
hierarchy.py intocado.
