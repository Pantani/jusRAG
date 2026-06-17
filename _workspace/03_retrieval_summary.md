# Fase 3 — Embeddings + Qdrant + /search (v0.3) — retrieval

Data: 2026-06-16. Agente: retrieval. Skills: legal-rag-contracts, legal-rag-safety.

## Arquivos criados

embeddings: `packages/embeddings/{base,fake_provider,openai_provider}.py` (+ `__init__`).
storage: `packages/storage/{base,payload,memory,qdrant,postgres,repositories,opensearch}.py` (+ `__init__`).
rag: `packages/rag/{types,query_analyzer,legal_ranker,retriever,hybrid_retriever,reranker,context_builder,search_service}.py` (+ `__init__`).
api: `apps/api/routes/search.py`; wiring em `apps/api/dependencies.py` (+ `main.py` include_router — coordenado, só adição).
jobs: `apps/worker/jobs/{chunk_jsonl,index_cdc,search_demo}.py`.
testes: `tests/unit/conftest.py`, `tests/unit/embeddings/test_fake_provider.py`,
`tests/unit/storage/{test_memory_store,test_qdrant_store}.py`,
`tests/unit/rag/{test_legal_ranker,test_retriever}.py`, `tests/integration/test_search.py`.
pyproject: adicionadas deps `qdrant-client>=1.12`, `openai>=1.54`.

## Abordagem do fake embedding (determinístico, sem rede)

Embedding lexical: hashed bag-of-words sobre vocabulário normalizado, projetado em
vetor de dim fixa (256) e L2-normalizado → cosseno reflete sobreposição lexical/conceitual.
Determinismo: NFKD fold + lowercase + remoção de stopwords PT + hash estável `blake2b`
(não o `hash()` salgado do Python). Sinal semântico além da superfície via:
(a) destem PT leve (defeitos→defeito, produtos→produto, vícios→vício); (b) mapa de
sinônimos jurídicos (desistência/desistir/devolução→arrependimento; produtor→fabricante).
Vício mantido como conceito distinto de defeito (institutos diferentes do CDC: fato vs
vício do produto). TF sublinear (1+log) amortece repetição para que chunks verbosos não
suplantem o artigo on-point. NÃO é um modelo real — captura só sobreposição lexical/conceitual;
o `OpenAIEmbeddingProvider` o substitui em produção via o mesmo Protocol.

## Prova dos casos de aceite (§19) — contra os dados REAIS (data/generated/cdc_chunks.jsonl)

`make search-demo` (offline, FakeEmbeddingProvider + InMemoryVectorStore, 6 chunks reais):
- `defeito do produto` → **art. 12** (score 0.421) > art. 26 (0.399) > art. 18 (0.338). OK
- `direito de arrependimento e desistência da compra` → **art. 49** (0.391) > art. 18 (0.283). OK
- `prazo para reclamar de vício` → **art. 26** (0.449) > art. 18 (0.334). OK

Via TestClient (`tests/integration/test_search.py`, deps sobrescritas por fake+memory):
POST /search `defeito do produto` → results[0].citation.article == "12";
`direito de arrependimento` → "49"; resposta carrega `score`, `semantic_score`,
`citation{chunk_id,source_url,doc_type}` e `text` com heading "## Art. N".

## index-cdc real vs mock

`make index-cdc` (job `apps/worker/jobs/index_cdc.py`) usa `OpenAIEmbeddingProvider` +
`QdrantVectorStore` e é idempotente (point id = uuid5(chunk_id)). **NÃO verificável neste
ambiente**: `qdrant-client`/`openai` não instalados no venv e Qdrant não está rodando
(porta 6333 ConnectionRefused). Foram adicionados ao pyproject mas a instalação/rede não
estava disponível aqui. O caminho de indexação→busca foi validado pelo mesmo contrato §28
via `InMemoryVectorStore` + `ChunkRepository` (test_memory_store, search_demo). Revalidar o
index-cdc real com: `pip install -e .` (ou sync) + `make up` (Qdrant) + `OPENAI_API_KEY` no
`.env` + `make index-cdc`. NÃO foi alegado sucesso do index-cdc real.

## Saída de test/lint (capturada)

- pytest (in-process `pytest.main`, não mascarado pelo wrapper de shell): **RC 0**, 82 testes,
  zero FAILURES; único warning é `StarletteDeprecationWarning` benigno do TestClient.
- mypy strict (subprocess): **Success: no issues found in 50 source files** (RC 0).
- ruff check (subprocess): **All checks passed!** (RC 0); ruff format --check: 68 files já formatados.

## Contratos a observar pela Fase 4 (answer)

- Consuma `RetrievedChunk` (`packages/rag/types.py`): `text` já inclui o heading "## Art. N";
  `score` é o composto §38, `semantic_score` é o cosseno bruto; cite via `citation: CitationRef`
  (chunk_id estável = base de `legal_basis[].citations`).
- Use `context_builder.build_context(chunks) -> BuiltContext{text, citations, chunks}` como
  entrada do AnswerWriter (selected_context). Não reimplemente recuperação.
- `SearchService`/`LegalRetriever` recebem `EmbeddingProvider`+`VectorStore` por Protocol;
  injete fake+memory em teste (vide `dependency_overrides` em test_search.py). Sem rede em unit.
- doc_type filtra statute/case_law (Fase 6): retriever já passa o filtro ao store.
- Shapes novos registrados em CONTRACTS.md (VectorSearchResult, RetrievalQuery, RetrievedChunk,
  CitationRef, SearchRequest/Response). Mudança nesses shapes → atualizar CONTRACTS.md e avisar.
