# Fase 11 — AD-2 fix: POST /ask roteado via grafo agentic (Opção A)

## Escopo
Defeito: a rota HTTP `POST /ask` usava `AnswerWriter` direto, cujo gate de escopo é
o `_MIN_SEMANTIC_SCORE = 0.20` (heurística do embedder léxico fake). Para
"Qual a alíquota do imposto de renda sobre criptomoedas?" a Súmula 543/CDC passou
no gate por sobreposição lexical pobre porém positiva, então o writer respondia
`answered` citando uma súmula irrelevante. O runtime LangGraph
(`packages.agents.graph.run_graph`) já recusava corretamente via `LegalAreaClassifier`
(§15.2); o `ask_demo` (AD-1) já tinha sido roteado pelo grafo. Faltava aplicar a
mesma Opção A à rota HTTP.

## Opção escolhida: A (graph-only, sem flag)

Removi o caminho direto pelo `AnswerWriter` da rota HTTP. Trade-off:

| Critério | A (graph-only, sem flag) — escolhida | B (flag `enable_agent_graph`, default true) |
|---|---|---|
| Coerência com Fase 7 | Total: o "runtime" é o grafo. | Mantém dois pipelines vivos. |
| Diff | Mínimo (rota delega a `AnswerService.ask`). | Maior: branch dual em `dependencies.py`, novo setting, doc, teste do toggle. |
| Risco de regressão | Baixo: `AnswerWriter` ainda existe (usado por evals/Fase 8), só não é mais o caminho de produção. | Médio: gate frágil continua acessível por env var. |
| Vitrine | Uma única narrativa de runtime. | "às vezes recusa, às vezes não" dependendo de `.env`. |
| Settings | Sem mudança (proibido pelo ownership). | Exigiria mexer em `settings.py` (proibido). |

Como `settings.py` está fora do meu ownership e a coerência com Fase 7 manda no
caminho mais limpo, Opção A foi adotada **sem flag**. O `AnswerWriter` segue
intocado para reuso em evals (§8), CitationAuditor (§31) e testes unitários
existentes — só não é mais o caminho de `/ask`.

## Mudanças

### `apps/api/dependencies.py`
- Removi `get_answer_writer`/`AnswerWriterDep` (rota não consome mais o writer
  direto na produção).
- Adicionei `AnswerService` (graph-backed): constrói o grafo §14 uma vez por
  instância via `build_graph(search=..., llm=..., buffer=AnswerBuffer())`,
  reusando as **mesmas** instâncias selecionadas por
  `make_embedding_provider`/`make_llm_provider`/`QdrantVectorStore` (sem
  duplicar a lógica de seleção). Por request:
    - gera `run_id = uuid4().hex`,
    - invoca com `LegalResearchState(run_id, question, jurisdiction="BR")`,
    - rehidrata `LegalResearchState` via `model_validate`,
    - lê `AnswerResponse` do `AnswerBuffer` (None ⇒ recusa pré-síntese),
    - mapeia para o shape público com `_to_answer_response`.
- Mapeamento:
    - `status`: `state.status == "answered"` → `AnswerStatus.ANSWERED`, qualquer
      outro (refused/needs_more_info/failed/running) colapsa para
      `AnswerStatus.REFUSED` (nunca expor resposta meio pronta).
    - `caveats`: vindas do `state.caveats` (já carregam disclaimer §41 do
      `risk_checker`).
    - `audit`: `state.audit` → `CitationAudit` traduzindo o rename
      `unsupported_claim_rate` → `unsupported_legal_claim_rate`. `None` quando
      a recusa ocorreu antes da auditoria (não inventa verdict).
    - Sem buffered answer: `build_refusal(BuiltContext("",[],[]))` + caveats do
      state. `sources=[]` (nada recuperado em escopo, §22).
- `top_k`/`filters` ainda aceitos para estabilidade de wire (e por compat com
  `AnswerRequest`); o grafo §14 governa profundidade (per-researcher
  `top_k=8`) e filtros de escopo (`LegalAreaClassifier` + `doc_type`). Threading
  request-level por nó acoplaria a rota ao interno do grafo — fora do escopo.
  Marcado com `# noqa: ARG002` + docstring.

### `apps/api/routes/ask.py`
- Delega a `AnswerServiceDep.ask`. Nada de gate semantic-score na rota.
- Docstring atualizada: cita AD-2/AD-1, scope gate via classifier (§15.2),
  `not_legal_advice=true` invariante.

### `tests/integration/test_ask.py`
- `test_ask_out_of_scope_refuses` reforçado: além de `status=refused` e
  `legal_basis=[]`, agora exige `case_law=[]` **e** `sources=[]`. É exatamente
  o invariante que AD-2 quebrava (a rota citava Súmula 543 com sources não
  vazios). Mantém os outros 6 testes intactos: o shape público é idêntico, o
  `top_k` na request continua aceito.

## Validação

### Suite local (offline, sem rede — fakes)

```
$ source .venv/bin/activate
$ python -m pytest
... 166 passed, 1 warning in 1.11s
$ ruff check .
All checks passed!
$ mypy packages apps
Success: no issues found in 90 source files
```

### Stack docker compose (api/postgres/qdrant/redis up, EMBEDDING_PROVIDER=fake, LLM_PROVIDER=fake, 11 chunks indexados dim=256)

`docker compose up -d --build api` → imagem reconstruída, container `recreated`,
`READY` após `/health` 200.

#### (a) `/ask` defeito → answered cita art. 12

```
POST /ask {"question":"O fornecedor responde por defeito do produto?","top_k":5}
```

```json
{
    "status": "answered",
    "short_answer": "Com base em Código de Defesa do Consumidor (Lei nº 8.078/1990), art. 26, ...",
    "legal_basis": [
        {"text":"... art. 26 ...","citations":["cdc-8078-1990-art-26"]},
        {"text":"... art. 14: O fornecedor de serviços responde, independentemente da existência de culpa, pela reparação dos danos causados aos consumidores por defeitos relativos à prestação dos serviços ...","citations":["cdc-8078-1990-art-14"]},
        {"text":"... art. 12: O fabricante, o produtor, o construtor, nacional ou estrangeiro, e o importador respondem, independentemente da existência de culpa, pela reparação dos danos causados aos consumidores por defeitos ...","citations":["cdc-8078-1990-art-12"]},
        {"text":"... art. 18: Os fornecedores de produtos de consumo duráveis ou não duráveis respondem solidariamente pelos vícios de qualidade ...","citations":["cdc-8078-1990-art-18"]}
    ],
    "case_law": [],
    "caveats": ["Não foi recuperada jurisprudência aplicável; a análise se apoia na legislação.", "A conclusão pode depender de prova, documentos e datas do caso concreto.", "Esta resposta tem finalidade informativa ..."],
    "sources": [
        {"chunk_id":"cdc-8078-1990-art-26", "article":"26", "doc_type":"statute", "source":"planalto", ...},
        {"chunk_id":"cdc-8078-1990-art-14", "article":"14", ...},
        {"chunk_id":"cdc-8078-1990-art-12", "article":"12", ...},
        {"chunk_id":"cdc-8078-1990-art-18", "article":"18", ...}
    ],
    "not_legal_advice": true,
    "audit": {"citation_coverage": 1.0, "unsupported_legal_claim_rate": 0.0, "unsupported_claims": [], "passed": true}
}
```

Art. 12 presente em `legal_basis`/`sources`. Auditoria passou
(citation_coverage=1.0, unsupported=0.0).

#### (b) `/ask` cripto → refused, sources=[], sem inventar súmula

```
POST /ask {"question":"Qual a alíquota do imposto de renda sobre criptomoedas?","top_k":5}
```

```json
{
    "status": "refused",
    "short_answer": "Não há base suficiente nas fontes recuperadas para responder a esta pergunta com segurança. Reformule a pergunta ou consulte um profissional habilitado.",
    "legal_basis": [],
    "case_law": [],
    "caveats": [
        "A base atual cobre principalmente Direito do Consumidor; a pergunta parece ser de área 'tax'.",
        "A conclusão pode depender de prova, documentos e datas do caso concreto.",
        "Esta resposta tem finalidade informativa e foi gerada com base nas fontes recuperadas pelo sistema. Ela não substitui a análise de um advogado ou profissional habilitado ..."
    ],
    "sources": [],
    "not_legal_advice": true,
    "audit": null
}
```

`status=refused`, `legal_basis=[]`, `case_law=[]`, `sources=[]`, **nenhuma**
Súmula 543 (nem qualquer súmula CDC) citada. Caveat do classifier indicando a
área `tax`. `audit=null` porque a recusa ocorre antes da auditoria (graph route
`refusal` ⇒ `check_risks`, sem `synthesize_answer`/`audit_citations`).

#### (c) `/health` 200

```
$ curl -s -w "\nHTTP=%{http_code}\n" http://localhost:8000/health
{"status":"ok"}
HTTP=200
```

## Aceite (todos OK)

- `make test` (166 passed) — incluindo `tests/integration/test_ask.py` reforçado
  com `case_law==[]` e `sources==[]` no cenário out-of-scope.
- `make lint` (ruff clean + mypy strict, 90 source files).
- HTTP `/ask` defeito → `answered` cita `cdc-8078-1990-art-12`.
- HTTP `/ask` cripto → `refused`, `sources=[]`, sem súmula irrelevante.
- `not_legal_advice=true` em ambas (formato invariante §30/§41).

## Flag

Nenhuma. Opção A pura, conforme acordado quando "a coerência for total" — não
sobrou dead code de produção.

## Coordenação / próximos passos

- `_workspace/CONTRACTS.md` (Fase 7) ainda diz "`/ask` sob `ENABLE_AGENT_GRAPH=true`
  NÃO integrado ainda (ponto de entrada `run_graph` pronto; integração coordenada
  com answer/foundation)". Essa nota está stale: a integração foi feita e o flag
  não existe. **Pendência (FoundationAgent)**: atualizar essa seção do CONTRACTS
  para refletir AD-2.
- `AnswerWriter` (`packages/answer/answer_writer.py`) e seus testes seguem em uso
  para Fase 8 (`packages/evals/harness.py`) — não foram tocados.
