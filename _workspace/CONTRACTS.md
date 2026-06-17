# CONTRACTS.md — shapes compartilhados (dono: legal-domain)

Fonte normativa: Prompt Master §8 (schemas), §9 (payloads RAG), §39 (autoridade).
Toda mudança de shape passa pelo `legal-domain` agent e reflete aqui.

## Enums — `packages/legal_types/enums.py` (StrEnum)

- `DocType`: statute, case_law, precedent, doctrine, unknown
- `LegalArea`: consumer, civil, labor, constitutional, tax, criminal, administrative, unknown
- `Source`: planalto, stf, stj, tj, doctrine, blog, unknown
- `Jurisdiction`: federal, state, municipal, unknown
- `PrecedentType`: binding_precedent, repetitive_appeal, general_repercussion, binding_summary, summary, ordinary_case_law, unknown
- `SupportLevel`: direct, supporting, related, unsupported
- `NormType`: constituicao, lei, lei_complementar, decreto, medida_provisoria, unknown

## Schemas — `packages/legal_types/schemas.py` (Pydantic v2)

### SourceMetadata (provenance, §18/§40.4)
`source: Source`, `source_url: str|None`, `version: str`, `content_hash: str`,
`ingested_at: datetime`, `is_current: bool = True`

### LegalDocument (§8)
`document_id, doc_type: DocType, source: Source, title, legal_area: LegalArea|None,
country="BR", jurisdiction: str|None, norm_type: str|None, norm_number: str|None,
norm_year: str|None, version, source_url: str|None, content_hash, created_at: datetime,
metadata: dict`

### LegalChunk (§8) — fields do documento + endereço estrutural
campos do LegalDocument exceto `document_id` (mantém) +
`chunk_id, article: str|None, paragraph: str|None, inciso: str|None, alinea: str|None,
text: str (min_length=1)`. Defaults: `country="BR"`, `metadata={}`.

### LegalCitation (§8)
`citation_id, source: Source, doc_type: DocType, title, source_url: str|None,
article: str|None, case_number: str|None, court: str|None, judgment_date: date|None,
publication_date: date|None, support_level: SupportLevel, chunk_id: str|None`

### CaseLawDocument (§8) — `doc_type` fixo = case_law
`document_id, doc_type: Literal[DocType.CASE_LAW], source: Source, court: str,
case_number: str|None, rapporteur: str|None, panel: str|None, judgment_date: date|None,
publication_date: date|None, legal_area: LegalArea|None, precedent_type: PrecedentType|None,
is_binding: bool=False, ementa: str|None, full_text: str|None, source_url: str|None,
content_hash, metadata: dict`

## Citações — `packages/legal_types/citations.py`

- `slugify(str) -> str`
- `build_chunk_id(*, short_name, norm_number, norm_year, article=None, paragraph=None, inciso=None, alinea=None) -> str`
  Ex.: `cdc-8078-1990-art-12`, `cdc-8078-1990-art-6-par-1-inc-i`. Determinístico (idempotência §40.4).
- `citation_from_chunk(chunk, *, support_level=DIRECT, citation_id=None) -> LegalCitation`
- `citation_from_case_law(doc, *, support_level=SUPPORTING, title=None, chunk_id=None) -> LegalCitation`
- `format_citation(LegalCitation) -> str`

## Hierarquia de autoridade — `packages/legal_types/hierarchy.py` (§39)

`AuthorityTier` + `AUTHORITY_WEIGHTS`: constitution 1.00, federal_law 0.95 (lei federal/súmula
vinculante/STF RG), stj_repetitive 0.90, stj_summary 0.88, stj_case_law 0.75, tj 0.60,
doctrine 0.40, blog 0.20, unknown 0.10.
Helpers: `weight_for(tier)`, `tier_for_statute(chunk)`, `tier_for_case_law(doc)`,
`authority_weight_for_chunk(chunk)`, `authority_weight_for_doc_type(doc_type)`.

## Vigência temporal — `packages/legal_types/temporal_validity.py`

`parse_version_date(str)->date` (ValueError em formato inválido, sem fallback),
`is_current(chunk)->bool` (lê `metadata['is_current']`, default True),
`current_chunks(iter)->list`, `select_version_at(chunks, date)->LegalChunk|None`,
`latest_version(chunks)->LegalChunk|None`.

## Camada de recuperação — Fase 3 (dono: retrieval)

### EmbeddingProvider — `packages/embeddings/base.py` (Protocol, §27)
`embed_texts(list[str]) -> list[list[float]]`, `embed_query(str) -> list[float]`.
Impls: `FakeEmbeddingProvider` (determinístico, sem rede, hashed bag-of-words +
destem PT + sinônimos jurídicos + TF sublinear, L2-normalizado, dim=256 default),
`OpenAIEmbeddingProvider` (lazy import, lê settings; nunca em unit).

### VectorStore — `packages/storage/base.py` (Protocol, §28)
`upsert_chunks(chunks, vectors) -> None`, `search(query_vector, top_k, filters?) ->
list[VectorSearchResult]`. Impls: `QdrantVectorStore` (collection `legal_chunks`,
distance COSINE, point id = uuid5(chunk_id) → idempotente), `InMemoryVectorStore`
(testes/demos, ranqueia por cosseno). `payload.chunk_to_payload(chunk)` deriva o
payload §9; `FILTERABLE_KEYS = (doc_type, legal_area, source, article, norm_number,
norm_year, is_current)`.

### VectorSearchResult — `packages/storage/base.py` (dataclass frozen)
`chunk_id: str`, `score: float` (cosseno bruto), `text: str`,
`payload: dict`, `metadata: dict`.

### Retriever I/O — `packages/rag/types.py` (§29)
- `RetrievalQuery`: `query, top_k=8, legal_area?, doc_type?, filters: dict`.
- `RetrievedChunk` (saída do retriever, consumido por answer/agentic):
  `chunk_id, text, score` (composto §38), `semantic_score` (cosseno bruto),
  `citation: CitationRef`, `metadata: dict`.
- `CitationRef`: `title, article?, source_url?, chunk_id, doc_type, source`.

Ranking composto MVP §38 em `packages/rag/legal_ranker.py`:
`0.70·semantic + 0.20·legal_authority + 0.10·exact_citation_match`. Authority via
norm_type (statute) / doc_type fallback (AUTHORITY_WEIGHTS §39). `exact_citation_match`
casa o nº do artigo extraído da query (`query_analyzer.extract_article`).
`context_builder.build_context(chunks) -> BuiltContext{text, citations, chunks}`.

### POST /search — `apps/api/routes/search.py`
Request `SearchRequest`: `{query: str(min 1), top_k: int(1..50, default 8),
filters?: dict}`. Response `SearchResponse`: `{query, top_k, results: SearchHit[]}`,
`SearchHit`: `{chunk_id, text, score, semantic_score, citation: CitationOut,
metadata}`, `CitationOut`: `{title, article?, source_url?, chunk_id, doc_type,
source}`. Rota só valida e delega a `SearchService` (DI em `dependencies.py`:
`get_embedding_provider`/`get_vector_store`/`get_search_service`, sobrescritíveis em teste).

## Camada de resposta — Fase 4 (dono: answer)

### LLMProvider — `packages/llm/base.py` (Protocol, §30)
`generate_answer(messages: list[LLMMessage], context: BuiltContext) -> LLMAnswerDraft`.
- `LLMMessage`: `{role: str, content: str}` (dataclass frozen).
- `LLMAnswerDraft`: `{short_answer: str, legal_basis: list[DraftLegalBasis],
  caveats: list[str], refused: bool=False}`.
- `DraftLegalBasis`: `{text: str, citations: list[str]}` (citations = chunk_ids).
Impls: `FakeLLMProvider` (determinístico, sem rede; sintetiza o draft SOMENTE do
`context`, nunca inventa artigo; `context.chunks==[]` → `refused=True`),
`OpenAILLMProvider` (lazy import; lê `OPENAI_API_KEY`/`OPENAI_CHAT_MODEL`; JSON estrito;
nunca em unit). A passagem do `BuiltContext` ao Protocol permite ao fake fundamentar
estritamente nas fontes; o provider real usa o texto do prompt.

### AnswerRequest/AnswerResponse — `packages/answer/schemas.py` (§30)
- `AnswerRequest`: `{question: str(min 1), top_k: int(1..50, default 8), filters?: dict}`.
- `AnswerStatus` (StrEnum): `answered | refused`.
- `AnswerResponse`: `{status: AnswerStatus, short_answer: str,
  legal_basis: LegalBasisItem[], case_law: CaseLawItem[], caveats: str[],
  sources: SourceItem[], not_legal_advice: Literal[True], audit: CitationAudit|None}`
  (`not_legal_advice` sempre true, §2.6/§41).
- `LegalBasisItem`: `{text: str, citations: str[]}` (citations = chunk_ids ⊆ sources).
  **Só legislação** — citações a chunks `case_law` são removidas daqui (separação §2.3).
- `CaseLawItem` (Fase 6): `{chunk_id, court?, case_number?, title, ementa, source_url?}`.
  Jurisprudência montada SOMENTE de chunks `doc_type=case_law` recuperados (court/case_number
  do `metadata`, ementa do `text`, source_url/title da `CitationRef`). Bloco vazio ⇒ omitido;
  nunca inventado (§22). Mantém legislação (`legal_basis`) e jurisprudência (`case_law`)
  visivelmente separadas (§2.3).
- `SourceItem`: `{chunk_id, title, article?, source_url?, doc_type, source}`
  (derivado de `CitationRef` do chunk recuperado).
Invariantes (formatter): `sources` sempre presente quando responde; aviso §41 sempre
anexado a `caveats`; citações fora do contexto recuperado são removidas; recusa segura
→ `status=refused`, `legal_basis=[]`, `sources=[]`.

### AnswerWriter — `packages/answer/answer_writer.py` (§30)
`AnswerWriter(search_service, llm, min_semantic_score=0.20)`;
`write(question, top_k=8, filters?) -> AnswerResponse`. Pipeline:
retrieve **separado** (`SearchService.search_separated` → `statutes[]`, `case_law[]`) →
filtra cada bloco por `semantic_score >= min_semantic_score` → contexto = statutes+case_law
(legislação primeiro) → `LLMProvider.generate_answer` → `formatter.build_answer(draft,
context, grounded_case_law)` → auditoria. Recusa segura quando NEM statute NEM case_law em
escopo (§2.2; antes era só statute), ou `draft.refused`, ou auditoria reprova. O bloco
`case_law` da resposta é montado dos chunks `case_law` recuperados (§22); o LLM/auditor veem
ambos os blocos, então súmula alucinada é detectada. `min_semantic_score` é heurística calibrada para o
`FakeEmbeddingProvider` (cosseno léxico sobre o seed de 6 artigos); controle de escopo
robusto vem do Area Classifier (Fase 7) + CitationAuditor (Fase 5).

### POST /ask — `apps/api/routes/ask.py`
Request `AnswerRequest`, Response `AnswerResponse` (acima). Rota só valida e delega ao
`AnswerWriter` (DI em `dependencies.py`: `get_llm_provider`/`get_answer_writer`,
sobrescritíveis em teste; override de `get_llm_provider` deve retornar uma instância
via `lambda`, não a classe). Prompts §32 em `packages/answer/prompts.py`.

### Para a Fase 5 (CitationAuditor) — entrada esperada
Recebe `answer: AnswerResponse` + `selected_context: BuiltContext` (+ `sources`).
Cada `legal_basis[].citations` já é ⊆ `sources[].chunk_id` (garantido pelo formatter),
mas o auditor deve re-extrair claims do `short_answer`/`legal_basis[].text` e verificar
suporte contra `BuiltContext.chunks[].text`, calculando `citation_coverage` e
`unsupported_legal_claim_rate`, e reescrever/remover claims sem suporte (§31).

## Camada de auditoria — Fase 5 (dono: answer / CitationAuditAgent)

### CitationAuditor — `packages/answer/citation_auditor.py` (§31)
Função pura, determinística, sem rede. API reusável pelo eval-agent:
- `audit_claims(short_answer: str, legal_basis: list[LegalClaim], chunks:
  list[AuditChunk], *, max_unsupported_rate=0.05) -> CitationAuditResult`.
- `extract_claims(short_answer, legal_basis) -> list[LegalClaim]`: cada `legal_basis`
  é um claim; sentenças do `short_answer` com referência a artigo ou marcador jurídico
  viram claims. Split de sentenças protege abreviações (`art.`, `inc.`, `par.`…).
- Dataclasses frozen: `AuditChunk{chunk_id, text}`, `LegalClaim{text, cited_ids:tuple}`,
  `CitationAuditResult{citation_coverage, unsupported_legal_claim_rate,
  unsupported_claims:list[str], passed:bool}` (+ `.as_dict()`).
- Suporte de um claim: algum chunk (restrito aos `cited_ids` quando há citação) cuja
  sobreposição léxica (Jaccard sobre tokens sem acento/stopwords, `_MIN_OVERLAP=0.18`)
  com o texto do claim ≥ limiar **e** que contenha todo artigo citado pelo claim
  (`art. N`) **e** toda súmula citada (`Súmula N`; Fase 6). Artigo/súmula alucinado (não
  recuperado) → sempre `unsupported`. Número de súmula é casado também no `chunk_id`
  (`stj-sumula-297`). Sem claim jurídico → cobertura 1.0 (vacuamente suportado).
- `passed = unsupported_legal_claim_rate <= 0.05` (§36). Saída no shape EXATO §31.

### Nó de runtime — `packages/agents/citation_auditor.py` (§12.8, Fase 7)
Função pura (sem LangGraph ainda): `audit_answer(answer: AnswerResponse, context:
BuiltContext) -> CitationAuditResult` adapta `legal_basis[]→LegalClaim` (carregando
`citations` em `cited_ids`) e `context.chunks→AuditChunk`. `run_citation_audit_node`
é o entrypoint que o grafo da Fase 7 chamará para preencher `LegalResearchState.audit`.

### Integração no AnswerWriter (§30 → §31)
`AnswerWriter.write` agora: retrieve → context → LLM → `formatter.build_answer` →
**auditoria**. Se o audit não passa: reescreve conservador (remove os `legal_basis`
cujo `text` está em `unsupported_claims`; se o `short_answer` foi flagado, adota o
primeiro basis suportado), re-audita o resultado; se sobrar < 1 basis suportado ou o
re-audit ainda falhar → **recusa segura** (`status=refused`, `legal_basis=[]`). O
`CitationAudit` resultante é sempre anexado à resposta. Recusa não depende mais só do
`_MIN_SEMANTIC_SCORE` (primeira passada heurística), o gate robusto é o auditor.

### Campo `audit` do AnswerResponse — `packages/answer/schemas.py`
`AnswerResponse.audit: CitationAudit | None = None`, onde
`CitationAudit{citation_coverage:float, unsupported_legal_claim_rate:float,
unsupported_claims:list[str], passed:bool}` (mesmo shape §31, serializável na resposta
HTTP `/ask`). `None` apenas em respostas que não passaram pela auditoria (não ocorre
no fluxo atual: toda resposta answered/refused pós-auditoria carrega `audit`).

### Para o eval-agent (Fase 5 evals)
Reusar `audit_claims` / `audit_answer` e as métricas `citation_coverage` e
`unsupported_legal_claim_rate` do `CitationAuditResult`. Threshold v1 (§36):
`unsupported_legal_claim_rate ≤ 0.05`. NÃO relaxar o limiar para passar testes de
alucinação — bug = corrigir extração/verificação no auditor.

## Camada de jurisprudência — Fase 6 (dono: ingestion / CaseLawAgent)

### Seed STJ — `data/seed/case_law/stj_consumer_seed.jsonl`
JSONL de súmulas públicas reais do STJ (consumer): por linha `summary_number, court,
source, precedent_type, is_binding, legal_area, judgment_date, publication_date,
ementa, source_url`. Sem PII/sigiloso (§40). 5 entradas (Súmulas 297, 302, 130, 479, 543).

### StjCaseLawLoader — `packages/ingestion/loaders/stj.py`
`load() -> list[CaseLawDocument]`. `document_id=slugify("STJ-sumula-<n>")` (`stj-sumula-297`),
`case_number="Súmula <n>"`, ementa normalizada, `content_hash=sha256(ementa)`,
`precedent_type=summary`, `is_binding=False`. `StfCaseLawLoader` (`stf.py`) é placeholder
(`NotImplementedError`) para fase futura.

### Chunker de ementa — `packages/ingestion/chunker.py`
`chunk_case_law(doc) -> LegalChunk | None` e `chunk_case_law_documents(docs) -> list`.
**Não há novo tipo de chunk**: jurisprudência vira `LegalChunk` com `doc_type=case_law`,
`chunk_id=document_id`, `text=ementa`, `version=judgment_date.iso`. O payload §9 de
jurisprudência (court, case_number, rapporteur, panel, precedent_type, is_binding,
judgment_date, publication_date) viaja em `metadata` → projetado por `chunk_to_payload`
sem alterar `payload.py`. Sem ementa → não emite (§22).

### Job — `apps/worker/jobs/ingest_case_law.py`
`python -m apps.worker.jobs.ingest_case_law` → `data/generated/case_law_chunks.jsonl`
(mesmo shape `LegalChunk` JSONL do `ingest_cdc`). Idempotente por `content_hash`,
byte-estável com `created_at` fixo. **Pendência orquestrador**: `make ingest-case-law`
e incluir o JSONL na indexação (collection `legal_chunks`).

### Para retrieval (Fase 6, dono: retrieval)
Filtrar jurisprudência com `filters={"doc_type": "case_law"}` (já em `FILTERABLE_KEYS`);
statute com `{"doc_type": "statute"}`. Metadados de citação de case_law no `metadata`/payload
do resultado. `schemas.py` NÃO foi estendido (CaseLawDocument já bastava).

## Camada de recuperação — Fase 6 (dono: retrieval): separação statute/case_law

### Indexação (statute + case_law na mesma collection)
`apps/worker/jobs/index_cdc.py` (via `load_indexable_chunks()` em `chunk_jsonl.py`) indexa
`cdc_chunks.jsonl` + `case_law_chunks.jsonl` (quando presente) em `legal_chunks`. Idempotente
por `chunk_id`. `load_case_law_chunks()` retorna `[]` se o JSONL não existe → jurisprudência
só é indexada/exibida com fonte (§22). Comando: `make ingest-cdc` →
`python -m apps.worker.jobs.ingest_case_law` → `make index-cdc`. PENDÊNCIA Makefile (Foundation):
`make ingest-case-law`.

### Ranking de autoridade para case_law (§39)
`legal_ranker.authority_for_payload` resolve `case_law` por `payload["metadata"]`
(`precedent_type`/`court`): **STJ súmula = 0.88** (STJ_SUMMARY), STJ acórdão 0.75, STF 0.95,
TJ 0.60. (Antes caía no fallback 0.75 por doc_type.)

### Recuperação separada — `packages/rag/retriever.py`
`SeparatedRetrieval{statutes: list[RetrievedChunk], case_law: list[RetrievedChunk]}` via
`LegalRetriever.retrieve_separated(RetrievalQuery)` (duas buscas doc_type-filtradas, cada bloco
ranqueado/truncado a `top_k`). `SearchService.search_separated(query, top_k, filters?)` expõe
ao app. `case_law=[]` quando nenhuma fonte de jurisprudência foi recuperada (nunca inventa, §22).

### POST /search (estendido)
`SearchRequest` ganha `separate: bool=False`. Quando `true`, `SearchResponse` carrega
`separated: {statutes: SearchHit[], case_law: SearchHit[]}` além de `results`. Cada `SearchHit`
já traz `citation.doc_type ∈ {statute, case_law}`. Sem `separate`, comportamento Fase 3 inalterado;
filtro `{"doc_type": ...}` continua válido.

### Consumo pelo answer
Renderizar §32: "Fundamento legal" ← `statutes`; "Jurisprudência relevante" ← `case_law`
(omitir bloco vazio). Alternativa: `search(..., filters={"doc_type": "statute"|"case_law"})`.
`RetrievedChunk`/`CitationRef` NÃO mudaram (já carregavam `doc_type`); novidade = `SeparatedRetrieval`
+ flag `separate`.

## Notas de payload RAG (§9) — consumido por ingestion/storage/retrieval

O payload do vector DB é derivado do `LegalChunk`/`CaseLawDocument`. Statute inclui
`is_current` e `version`; case_law inclui `precedent_type`/`is_binding`. `content_hash`
no formato `sha256:<hex>`. Enums serializam como string (StrEnum).

## Camada agentic — Fase 7 (dono: agentic) — LangGraph runtime

### LegalResearchState efetivo — `packages/agents/state.py` (§13, Pydantic v2, EXATO)
Sem campos extras além de §13. `status: Literal["running","needs_more_info","answered",
"refused","failed"] = "running"`.
- `RetrievedSource`: `chunk_id, doc_type, title, text, score, source_url: str|None=None,
  metadata: dict`.
- `CitationAuditResult`: `citation_coverage, unsupported_claim_rate (NB: rename de §31
  unsupported_legal_claim_rate), unsupported_claims: list[str], passed: bool`.
- `LegalResearchState`: `run_id, question, jurisdiction="BR", legal_area: str|None,
  facts: dict, missing_facts: list[str], retrieved_statutes/retrieved_case_law/
  selected_context: list[RetrievedSource], draft_answer/final_answer: str|None,
  caveats: list[str], audit: CitationAuditResult|None, status, errors: list[str]`.

### Grafo — `packages/agents/graph.py` (§14)
`build_graph(*, search: SearchService, llm: LLMProvider, buffer?, collector?) -> CompiledStateGraph`
e `run_graph(question, *, run_id, search, llm, jurisdiction="BR", collector?) -> LegalResearchState`.
Nós (nomes dos nós LangGraph): `intake, classify_legal_area, retrieve_statutes,
retrieve_case_law, analyze_precedents, rerank_and_select_context, synthesize_answer,
audit_citations, retry_synthesis, needs_more_info, check_risks`. Cada nó é
`Callable[[LegalResearchState], dict]` (update parcial). Roteamento §14 via 3 conditional
edges; retry de síntese cap=1 contado por `RETRY_MARKER` em `state.errors`.

### Contrato dos nós (reuso por quem integrar /ask)
- Researchers consomem `SearchService.search(q, top_k, {"doc_type":..., "legal_area":...})`
  e mapeiam `RetrievedChunk -> RetrievedSource` (`_adapters.chunk_to_source`).
- `synthesize_answer` reusa `build_context`/`build_answer` + `LLMProvider`; a `AnswerResponse`
  estruturada vive num `AnswerBuffer` por `run_id` (estado §13 carrega só `draft_answer` texto).
- `audit_citations` reusa `packages/answer/citation_auditor` (Fase 5) via `audit_answer`,
  convertendo para `state.CitationAuditResult` (`to_state_audit`).
- `check_risks` injeta caveats + disclaimer §41, seta `final_answer`/`status` terminal.

### Traces — `packages/agents/trace.py`
`TraceCollector.record(run_id, step, status, note)` + log `jusrag.agents`; `for_run(run_id)`.
`retry_attempts(errors)`/`visible_errors(errors)` (filtra `RETRY_MARKER`).

### Dep adicionada
`pyproject.toml [project.dependencies]`: `langgraph>=0.2` (instalado 1.2.5). Ratificação
pelo FoundationAgent pendente. `/ask` sob `ENABLE_AGENT_GRAPH=true` NÃO integrado ainda
(ponto de entrada `run_graph` pronto; integração coordenada com answer/foundation).

## Camada de avaliação — Fase 8 (dono: eval)

### Golden dataset — `data/seed/questions/consumer_golden.yaml`
Lista YAML, 31 perguntas (24 in-scope CDC/STJ + 7 out-of-scope). Por item: `id` (estável,
nunca renumerar — só append), `question`, `expected_chunk_ids` (chunk_ids do seed que DEVEM
ser recuperados), `expected_behavior ∈ {answered, refused}`, `expected_articles?`,
`expected_sumulas?`. Out-of-scope: `expected_chunk_ids: []` + `refused`. Fiel ao seed (sem
artigo/súmula inventado). Calibrado para o `FakeEmbeddingProvider` (recall@5=1.0).

### Loader — `packages/evals/golden.py`
`load_golden(path?) -> list[GoldenQuestion]` (valida shape, ids únicos, falha alto em arquivo
malformado). `GoldenQuestion{id, question, expected_chunk_ids, expected_behavior,
expected_articles, expected_sumulas, in_scope}`. `in_scope_questions` / `out_of_scope_questions`
/ `golden_stats`.

### Harness offline — `packages/evals/harness.py`
`build_harness() -> EvalHarness{search: SearchService, answer_writer: AnswerWriter,
indexed_count}` sobre `FakeEmbeddingProvider` + `InMemoryVectorStore` + `FakeLLMProvider`,
indexado com `load_indexable_chunks()`. Determinístico, sem rede — caminho de CI.

### Métricas — `retrieval_eval.py` / `answer_eval.py` / `citation_eval.py` (reuso)
- `evaluate_retrieval(harness, questions, k=5) -> RetrievalEvalReport` (recall@k micro-avg,
  gate `≥0.80`; precision@k informativo).
- `evaluate_answers(harness, questions, produced?) -> AnswerEvalReport`
  (`refusal_when_no_source_rate` sobre out-of-scope, gate `≥0.90`; `answer_relevancy` e
  `faithfulness` heurísticos, fora do gate). `produce_answers` roda o writer uma vez;
  `answer_cases_for_citation(harness, produced) -> list[AnswerCase]` adapta para o
  `citation_eval` usando o **texto real do chunk recuperado** (não a redação da resposta).
- `evaluate_citations` (Fase 5) reusado: `citation_coverage` (gate `≥0.90`) e
  `unsupported_legal_claim_rate` (gate `≤0.05`).

### Orquestrador + gate — `packages/evals/run_all.py`
`run_suite() -> EvalSuiteResult` (uma passada). `main()` escreve
`data/generated/eval_report.{json,md}`, imprime resumo, e **sai !=0** quando o gate falha.
Gate de alucinação (`unsupported_legal_claim_rate>0.05`) é SEMPRE aplicado; demais thresholds
§36 aplicados em modo estrito (default). `EVAL_GATE_STRICT=0` → só o gate de alucinação.
`make eval` (`python -m packages.evals.run_all`) já existe; exit code agora falha o build.

### Valores reais no seed (fake provider): TODOS passam o gate §36
recall@5=1.0 · citation_coverage=1.0 · unsupported_legal_claim_rate=0.0 ·
refusal_when_no_source_rate=1.0 (relevancy heurístico 0.958, faithfulness 1.0).
