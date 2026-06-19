# 14 — Sinal explícito OOS-determinístico vs. UNKNOWN-sem-evidência (§2.2)

## Problema
O PR #3 relaxou `_is_out_of_scope` (answer) para NÃO pré-recusar UNKNOWN sem-evidência
— correto para perguntas in-corpus cujo keyword erra (ex.: inventário enxuto). Mas
`classify_area` **colapsa** dois casos distintos em `UNKNOWN`:
- (a) termo de **regime sem corpus** explicitamente casado (`_out_of_scope_match`),
- (b) **ausência total de evidência**.

Sem distingui-los, regimes corpusless (INPI/marca, ambiental, eleitoral, marítimo...)
classificavam UNKNOWN, prosseguiam ao retrieval e eram respondidos com fonte espúria sob
FakeEmbedding — vazamento que viola §2.2 (regra #1).

## Solução (CodeRabbit opção 1)
Função pública pura/determinística em `packages/agents/classify_area.py`, expondo o sinal
sem alterar a semântica de `classify_area` (outros consumidores dependem):

```python
def matched_out_of_scope_regime(question: str) -> bool:
    return _out_of_scope_match(question.lower()) is not None
```

- True → OOS **determinístico** (regime corpusless casado): deve pré-recusar antes do
  retrieval, independe do embedding provider.
- False + área UNKNOWN → **sem-evidência**: prossegue ao retrieval (uma fonte real ainda
  pode surgir).

`administrative` resolve no enum (caveat via `is_in_scope`), mas TAMBÉM é corpusless →
conta como match aqui. Semântica de `classify_area`/`run_classify_area`/`is_in_scope`
intacta.

## Regimes cobertos (já em `_OUT_OF_SCOPE_TERMS`, boundary-match `\b`)
- Administrative: licitação, servidor/concurso público, improbidade, ato administrativo
- Previdenciário: previdência/previdenciár, INSS, aposentadoria, benefício previdenciário
- Empresarial/societário: sociedade empresária/limitada/anônima, falência, recuperação judicial
- Propriedade industrial: INPI, registro de marca, marca registrada, patente de invenção,
  propriedade industrial (marca/patente "soltos" ficam fora — genéricos demais)
- Ambiental: licenciamento ambiental, ambiental
- Eleitoral: eleitoral, candidatura
- Internacional/migratório: naturalização, extradição
- Marítimo: marítimo

Verificados todos os regimes pedidos. Sem novos termos adicionados — a cobertura
existente já contemplava o conjunto solicitado (vocabulário de domínio, sem overfit a
golden).

## Matriz de teste (`tests/unit/agents/test_classify_area.py`)
| Caso | Entrada | Esperado |
|------|---------|----------|
| INPI/marca | "Como registrar marca no INPI?" | True |
| Ambiental | "requisitos do licenciamento ambiental" | True |
| Previdenciário | "aposentadoria por tempo de contribuição" | True |
| Administrative | "regras de licitação para servidor público" | True |
| Empresarial | "pedido de recuperação judicial da sociedade limitada" | True |
| Eleitoral | "registro de candidatura no processo eleitoral" | True |
| Internacional | "extradição de estrangeiro e naturalização" | True |
| Marítimo | "transporte marítimo de cargas" | True |
| Improbidade | "ação de improbidade contra agente público" | True |
| **In-corpus sem-evidência** | "Quais os ritos do procedimento de arrolamento de bens do falecido?" | **False** (classify=UNKNOWN, regime=False) |
| In-scope consumer | "vício do produto e direito de arrependimento" | False |
| In-scope tax | "fato gerador do ICMS" | False |
| In-scope criminal | "homicídio culposo" | False |
| In-scope labor | "FGTS e aviso prévio" | False |
| In-scope civil | "usucapião extraordinária de imóvel" | False |
| **Held-out** concurso | "concurso público para o cargo de auditor" | True |
| **Held-out** previdência | "benefício previdenciário por incapacidade" | True |
| **Held-out** ato adm. | "ato administrativo e seus atributos de presunção" | True |

Teste dedicado confirma o caso (b): `classify_area(arrolamento...) == UNKNOWN` **e**
`matched_out_of_scope_regime(...) is False` — provando que distingue OOS de sem-evidência.

## Lint/test reais
- `uv run pytest tests/unit/agents/test_classify_area.py -q` → 53 passed
- `uv run pytest tests/unit/agents/ -q` → 65 passed (nenhum consumidor quebrado)
- `uv run ruff check ...` → All checks passed
- `uv run ruff check --select C901 ...` → All checks passed (CC<=10)
- `uv run mypy packages/agents/classify_area.py` → Success, no issues (strict)

Offline, determinístico, sem rede.

## Consumo (coordenado pelo answer)
`answer` deve chamar `matched_out_of_scope_regime(question)`: True → pré-recusa
pré-retrieval (§2.2); False com UNKNOWN → segue ao retrieval.
