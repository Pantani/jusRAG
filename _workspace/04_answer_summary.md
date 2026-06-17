# Fase 4 — /ask com resposta jurídica citada (v0.4) — answer

Data: 2026-06-17. Agente: answer. Skills: legal-rag-contracts, legal-rag-safety.

## Arquivos criados

llm: `packages/llm/{__init__,base,fake_provider,openai_provider}.py`.
answer: `packages/answer/{__init__,schemas,prompts,formatter,answer_writer}.py`.
api: `apps/api/routes/ask.py`; wiring em `apps/api/dependencies.py` (+ `main.py`
include_router — coordenado, só adição; `/health` e `/search` intactos).
jobs: `apps/worker/jobs/ask_demo.py`.
testes: `tests/unit/answer/{__init__,test_fake_llm_provider,test_formatter,test_answer_writer}.py`,
`tests/integration/test_ask.py`.

NÃO editei pyproject — nenhuma dependência nova necessária (`openai` já estava
declarado pela Fase 3; usado só com lazy import, nunca em unit).

## Shape do AnswerResponse (§30)

```
AnswerResponse {
  status: "answered" | "refused",
  short_answer: str,
  legal_basis: [{ text: str, citations: [chunk_id] }],   # citations ⊆ sources
  case_law: [],                                           # vazio até Fase 6
  caveats: [str],                                         # inclui aviso §41 sempre
  sources: [{ chunk_id, title, article?, source_url?, doc_type, source }],
  not_legal_advice: true                                  # sempre true (Literal)
}
```
`AnswerRequest { question: str(min 1), top_k: int(1..50, default 8), filters?: dict }`.

LLMProvider (§30): `generate_answer(messages, context: BuiltContext) -> LLMAnswerDraft`
com `LLMAnswerDraft { short_answer, legal_basis: [{text, citations}], caveats, refused }`.

## Recusa segura (§2.2, §2.3, §40)

Dois gates no AnswerWriter, sem inventar artigo em nenhum caso:
1. Nenhum chunk recuperado → recusa.
2. Nenhum chunk com `semantic_score >= 0.20` (out-of-scope) → recusa.
3. `draft.refused` do LLM → recusa.
O `_MIN_SEMANTIC_SCORE=0.20` é heurística calibrada para o `FakeEmbeddingProvider`
(cosseno léxico sobre o seed de 6 artigos): in-scope top ~0.23–0.32; pergunta
fora de escopo (IR sobre cripto) topa ~0.198 contra o artigo mais genérico. NÃO é
garantia semântica — controle robusto de escopo virá do Area Classifier (Fase 7) e
do CitationAuditor (Fase 5). É injetável (`min_semantic_score`) para recalibração com
embedding real. O formatter ainda remove qualquer citação fora do contexto recuperado.

## Prova dos 4 casos de aceite (§20)

Via `tests/integration/test_ask.py` (TestClient, deps fake+memory+FakeLLM, offline):
- (a) `test_ask_structured_shape`: POST /ask retorna `status, short_answer,
  legal_basis, case_law, caveats, sources`; `not_legal_advice is True`; `sources` não vazio.
- (b) `test_ask_in_scope_cites_art_12`: "O fornecedor responde por defeito do produto?"
  → `status="answered"`, `cdc-8078-1990-art-12` presente nas citações de legal_basis.
- (c) `test_ask_out_of_scope_refuses`: "Qual a alíquota do imposto de renda sobre
  criptomoedas?" → `status="refused"`, `legal_basis=[]`, `not_legal_advice=True`
  (NÃO inventa artigo).
- (d) `test_ask_never_cites_outside_context`: toda citação ⊆ `sources[].chunk_id`.
Extras: `test_ask_rejects_empty_question` (422); unit do fake LLM (determinístico +
recusa em contexto vazio + nunca cita fora do contexto), formatter (sources sempre +
aviso §41 + descarte de citação inventada + recusa), answer_writer end-to-end.

`make ask-demo` (dados REAIS `data/generated/cdc_chunks.jsonl`, offline):
- "O fornecedor responde por defeito do produto?" → `answered`,
  sources `[art-26, art-14, art-12]` (art. 12 citado; ordenação é do legal_ranker §38 da Fase 3).
- "Qual a alíquota do imposto de renda sobre criptomoedas?" → `refused`, sources `[]`.

## Saída de test/lint (capturada)

- pytest in-process (`pytest.main`; o wrapper de shell mascara a linha de resumo, igual
  Fase 3): **RC 0**, **97 testes coletados**, zero falhas; único warning é o
  `StarletteDeprecationWarning` benigno do TestClient.
- mypy (subprocess): **No issues found**.
- ruff check: **No issues found**; ruff format --check: **84 files already formatted**.

## Notas de integração

- O override de `get_llm_provider` em teste deve retornar **uma instância** via `lambda`
  (não a classe), senão o FastAPI interpreta `__init__(*args, **kwargs)` como query params
  → 422. Documentado em CONTRACTS.md.
- `OpenAILLMProvider`: lazy import de `openai`, lê `OPENAI_API_KEY`/`OPENAI_CHAT_MODEL`,
  `response_format=json_object`, `temperature=0`; parsing JSON estrito (sem fallback
  silencioso). **Não exercitado em unit** (sem rede).

## Contratos para a Fase 5 (CitationAuditor)

Entrada: `answer: AnswerResponse` + `selected_context: BuiltContext` (+ `sources`).
Já garantido pelo formatter: `legal_basis[].citations ⊆ sources[].chunk_id`. O auditor
deve re-extrair claims de `short_answer` + `legal_basis[].text`, verificar suporte contra
`BuiltContext.chunks[].text`, computar `citation_coverage` e `unsupported_legal_claim_rate`,
e reescrever/remover claims sem suporte (§31). Saída §31:
`{citation_coverage, unsupported_legal_claim_rate, unsupported_claims[], passed}`.
Bug do auditor = claim sem fonte passando → corrigir extração/verificação, não relaxar
threshold.
