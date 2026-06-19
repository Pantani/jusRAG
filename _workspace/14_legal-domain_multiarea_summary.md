# Fase A — legal-domain: expansão multi-área (7 códigos federais núcleo)

Dono: legal-domain. Ownership tocado: `packages/legal_types/enums.py`,
`packages/legal_types/hierarchy.py`, `tests/unit/legal_types/`, `_workspace/CONTRACTS.md`.
Nada fora desse ownership foi alterado.

## O que mudou

1. **`NormType.DECRETO_LEI` adicionado** (`enums.py`). Cobre os decretos-lei recepcionados com
   força de lei federal: CP (DL 2.848/1940), CPP (DL 3.689/1941), CLT (DL 5.452/1943).
   Mudança retrocompatível (append em StrEnum; valor `"decreto_lei"`). `decreto` regulamentar
   permanece distinto.

2. **`hierarchy.tier_for_statute`** tornou explícito o grupo força-de-lei via
   `_FEDERAL_LAW_NORMS = {lei, lei_complementar, decreto_lei, medida_provisoria}` → `FEDERAL_LAW`
   (0.95). `constituicao` → `CONSTITUTION` (1.00). A regra genérica `if norm:` permanece como
   fallback (comportamento inalterado), mas `decreto_lei` agora é garantido por conjunto explícito,
   protegendo contra futura regra infralegal para `decreto`.

3. **`LegalArea` NÃO foi estendido** — o enum já cobre `civil, criminal, labor, tax,
   constitutional` (além de consumer/administrative/unknown). Só documentei o mapeamento código→area.

4. **Testes** (ownership): `test_enums.py` ganhou cobertura de `NormType` (conjunto completo +
   distinção decreto_lei≠decreto); `test_hierarchy.py` ganhou
   `test_decreto_lei_maps_to_federal_law` (tier + peso 0.95). Nenhum teste existente quebrou.

5. **CONTRACTS.md** atualizado: linha `NormType`, bloco de mapeamento código→area, e o
   mapeamento `norm_type→tier` em hierarquia.

## Mapeamento norm_type → AuthorityTier (peso)

| norm_type | tier | peso |
|-----------|------|------|
| `constituicao` | CONSTITUTION | 1.00 |
| `lei` | FEDERAL_LAW | 0.95 |
| `lei_complementar` | FEDERAL_LAW | 0.95 |
| `decreto_lei` | FEDERAL_LAW | 0.95 |
| `medida_provisoria` | FEDERAL_LAW | 0.95 |
| `decreto` | FEDERAL_LAW (fallback genérico atual) | 0.95 |
| vazio / None | UNKNOWN | 0.10 |

Nota: `decreto` regulamentar tecnicamente seria infralegal, mas isso é comportamento
pré-existente fora do escopo desta fase. Não foi alterado (mudança cirúrgica).

## Mapeamento código federal → norm_type / LegalArea

| Código | norm | norm_type | LegalArea |
|--------|------|-----------|-----------|
| CF/88 | Constituição | `constituicao` | `constitutional` |
| Código Civil | Lei 10.406/2002 | `lei` | `civil` |
| Código Penal | DL 2.848/1940 | `decreto_lei` | `criminal` |
| CLT | DL 5.452/1943 | `decreto_lei` | `labor` |
| CTN | Lei 5.172/1966 | `lei` | `tax` |
| CPC | Lei 13.105/2015 | `lei` | `civil` (processo civil) |
| CPP | DL 3.689/1941 | `decreto_lei` | `criminal` (processo penal) |

Justificativa CPC→civil e CPP→criminal: o classificador de área opera sobre o ramo material;
processo civil é recuperado junto ao direito civil e processo penal junto ao penal. Mantém o
enum fechado existente sem inventar `procedural_civil`/`procedural_criminal`.

## Consumidores a revalidar (aviso ao orquestrador)

- **ingestion**: loaders dos 6 novos códigos devem setar `norm_type=decreto_lei` para CP/CPP/CLT
  e `legal_area` conforme tabela acima.
- **retrieval** (`packages/rag/legal_ranker.py`): NÃO requer mudança — `authority_for_payload`
  já resolve qualquer norm_type não-vazio≠constituição como FEDERAL_LAW (0.95). decreto_lei
  funciona out-of-the-box. Recomenda-se um teste de regressão lá confirmando 0.95 p/ decreto_lei.
- **eval**: golden multi-área deve cobrir as novas áreas; sem mudança de schema necessária.

## Resultado lint/test (real)

- `ruff check .` → **All checks passed!**
- `mypy packages apps` → **Success: no issues found in 94 source files**
- `pytest tests/unit/legal_types/` → **32 passed**
- `pytest tests/unit` (suíte completa, regressão de consumidores) → **150 passed**

Obs.: `make lint` falha no ambiente porque `mypy` não está no PATH do shell; rodado via
`.venv/bin/{ruff,mypy,pytest}` com sucesso. Isso é infra de ambiente, não regressão de código.
