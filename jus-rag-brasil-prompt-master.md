# Prompt Master — JusRAG Brasil

> Use este arquivo como especificação única para implementar o projeto `jus-rag-brasil` em fases, com agentes de implementação trabalhando em paralelo e com integração coordenada.

---

## 0. Papel do agente que receber este prompt

Você é um engenheiro sênior de IA, backend, RAG, agentes e legaltech. Sua tarefa é implementar um projeto open source chamado **JusRAG Brasil**.

O projeto deve ser executado por fases, com entregas incrementais, testes automatizados e integração contínua. Sempre que possível, divida o trabalho em agentes paralelos por módulo, evitando conflito de arquivos.

O projeto final deve demonstrar domínio de:

- RAG jurídico em português brasileiro.
- Ingestão e normalização de documentos jurídicos.
- Chunking jurídico por estrutura normativa.
- Vector search com metadata.
- Busca híbrida opcional.
- Reranking.
- Orquestração com agentes.
- Auditoria de citações.
- Avaliação de fidelidade.
- API robusta.
- Execução local com Docker.
- Documentação clara para GitHub.

---

## 1. Visão do produto

### Nome

```text
jus-rag-brasil
```

### Descrição curta

```text
Copiloto open source de pesquisa jurídica brasileira com RAG, citações verificáveis, auditoria de claims e avaliação de fidelidade.
```

### Frase para README

```text
Este projeto não fornece aconselhamento jurídico. Ele demonstra uma arquitetura de pesquisa jurídica assistida por IA, com RAG, fontes oficiais, citações verificáveis, versionamento jurídico e avaliação de fidelidade.
```

### Problema

LLMs conseguem gerar respostas jurídicas convincentes, mas podem inventar artigos, súmulas, decisões, teses, números de processo e fundamentos. Em direito, isso é crítico.

O projeto deve resolver o problema com uma arquitetura que:

- recupera fontes jurídicas antes de responder;
- cita as fontes usadas;
- separa legislação, jurisprudência e ressalvas;
- audita afirmações sem suporte;
- recusa respostas quando não houver base suficiente;
- mede qualidade com evals.

### Escopo inicial

O MVP deve começar por **Direito do Consumidor**.

Motivos:

- O CDC é compacto e demonstrável.
- As perguntas são práticas.
- É fácil criar dataset de avaliação.
- Permite mostrar legislação e jurisprudência em uma área clara.

### Fora do escopo da v1

Não implementar na v1:

- Uma LLM treinada do zero.
- Cobertura completa de todo o direito brasileiro.
- Peticionamento automático em produção.
- Aconselhamento jurídico definitivo.
- Ingestão de processos sigilosos.
- Armazenamento de dados pessoais sensíveis de usuários.

---

## 2. Regras fundamentais do sistema

Estas regras são obrigatórias em todos os módulos:

1. Nunca inventar artigo, lei, súmula, decisão, tese ou número de processo.
2. Toda afirmação jurídica relevante deve estar apoiada em uma fonte recuperada.
3. Quando não houver fonte suficiente, responder com recusa segura.
4. Separar claramente legislação, jurisprudência, interpretação e ressalvas.
5. Indicar quando a resposta depende de fatos adicionais.
6. Incluir aviso de que a resposta não é aconselhamento jurídico.
7. Manter fonte, URL, versão, data de ingestão e hash do conteúdo.
8. Escrever testes para lógica crítica.
9. Não colocar lógica de negócio dentro das rotas FastAPI.
10. Usar interfaces para embeddings, vector store, reranker e LLM provider.
11. Não commitar secrets, tokens, chaves de API ou dumps grandes.
12. Logs de perguntas devem ser anonimizáveis e desativáveis.
13. Testes não devem depender de rede externa por padrão.
14. Em ambiente local, usar dados seed pequenos e reproduzíveis.
15. A documentação deve explicar limitações, riscos e uso correto.

---

## 3. Stack técnica obrigatória

### Backend

```text
Python 3.12+
FastAPI
Pydantic v2
pydantic-settings
pytest
ruff
mypy
```

### IA / RAG

```text
OpenAI embeddings via interface abstrata
LLM provider via interface abstrata
LangGraph para orquestração a partir da fase agentic
Qdrant para vector search
OpenSearch opcional para BM25/hybrid search
Reranker opcional na v1, com interface preparada
```

### Infra local

```text
Docker Compose
Postgres
Qdrant
Redis
```

### Observabilidade e qualidade

```text
Logs estruturados
run_id por execução
traces simples por etapa
pytest
RAG evals
citation evals
GitHub Actions na v1
```

---

## 4. Arquitetura alvo

```text
Usuário
  ↓
Web UI ou API
  ↓
FastAPI
  ↓
Legal Query Analyzer
  ↓
Legal Area Classifier
  ↓
Retriever Router
  ├── Statute Retriever
  ├── Case Law Retriever
  ├── Precedent Retriever
  └── Metadata Retriever
  ↓
Hybrid Retrieval
  ├── Qdrant vector search
  ├── OpenSearch BM25, opcional
  └── metadata filters
  ↓
Reranker
  ↓
Legal Ranker
  ↓
Context Builder
  ↓
Answer Writer
  ↓
Citation Auditor
  ↓
Risk Checker
  ↓
Resposta final com fontes
```

---

## 5. Estrutura de diretórios obrigatória

Crie e mantenha esta estrutura:

```text
jus-rag-brasil/
  README.md
  LICENSE
  Makefile
  docker-compose.yml
  .env.example
  pyproject.toml

  apps/
    api/
      main.py
      dependencies.py
      routes/
        health.py
        ask.py
        search.py
        ingest.py
        evals.py
        sources.py
        runs.py

    worker/
      __init__.py
      jobs/
        ingest_cdc.py
        index_cdc.py
        ask_demo.py
        search_demo.py
        run_evals.py

    web/
      README.md
      # Streamlit no MVP ou Next.js depois

  packages/
    config/
      settings.py

    legal_types/
      schemas.py
      enums.py
      citations.py
      hierarchy.py
      temporal_validity.py

    ingestion/
      loaders/
        base.py
        local_markdown.py
        local_html.py
        planalto.py
        lexml.py
        stj.py
        stf.py
      normalizer.py
      chunker.py
      versioning.py

    embeddings/
      base.py
      openai_provider.py
      fake_provider.py

    llm/
      base.py
      openai_provider.py
      fake_provider.py

    storage/
      postgres.py
      qdrant.py
      opensearch.py
      repositories.py

    rag/
      query_analyzer.py
      retriever.py
      hybrid_retriever.py
      reranker.py
      legal_ranker.py
      context_builder.py

    agents/
      graph.py
      state.py
      intake.py
      classify_area.py
      statute_researcher.py
      case_law_researcher.py
      precedent_analyzer.py
      answer_writer.py
      citation_auditor.py
      risk_checker.py

    answer/
      prompts.py
      formatter.py
      schemas.py
      answer_writer.py
      citation_auditor.py

    evals/
      golden_questions.yaml
      retrieval_eval.py
      citation_eval.py
      answer_eval.py
      run_all.py

    observability/
      logging.py
      tracing.py
      cost_tracking.py

  data/
    seed/
      cdc/
        cdc.md
      questions/
        consumer_golden.yaml
    generated/
      .gitkeep

  docs/
    architecture.md
    source-policy.md
    legal-rag-design.md
    evaluation.md
    governance.md
    limitations.md
    demo-script.md
    roadmap.md

  tests/
    unit/
    integration/
    evals/
```

---

## 6. Comandos esperados

O projeto deve funcionar com estes comandos:

```bash
cp .env.example .env
make up
make test
make ingest-cdc
make index-cdc
make search-demo
make ask-demo
make eval
```

### Makefile alvo

```makefile
up:
	docker compose up --build

down:
	docker compose down -v

test:
	pytest

lint:
	ruff check .
	mypy packages apps

format:
	ruff format .

ingest-cdc:
	python -m apps.worker.jobs.ingest_cdc

index-cdc:
	python -m apps.worker.jobs.index_cdc

search-demo:
	python -m apps.worker.jobs.search_demo

ask-demo:
	python -m apps.worker.jobs.ask_demo

eval:
	python -m packages.evals.run_all
```

---

## 7. Variáveis de ambiente

Criar `.env.example`:

```env
APP_ENV=local
APP_NAME=jus-rag-brasil
LOG_LEVEL=INFO

POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=jus_rag
POSTGRES_USER=jus
POSTGRES_PASSWORD=jus

QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION_LEGAL_CHUNKS=legal_chunks

REDIS_URL=redis://redis:6379/0

OPENAI_API_KEY=
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4.1-mini

ENABLE_OPENSEARCH=false
OPENSEARCH_URL=http://opensearch:9200

STORE_RUN_LOGS=true
ANONYMIZE_RUN_LOGS=true
```

---

## 8. Modelos de domínio jurídico

Implementar em `packages/legal_types/schemas.py`.

### LegalDocument

Campos mínimos:

```text
document_id: str
doc_type: str
source: str
title: str
legal_area: str | None
country: str
jurisdiction: str | None
norm_type: str | None
norm_number: str | None
norm_year: str | None
version: str
source_url: str | None
content_hash: str
created_at: datetime
metadata: dict
```

### LegalChunk

Campos mínimos:

```text
chunk_id: str
document_id: str
doc_type: str
source: str
title: str
legal_area: str | None
country: str
jurisdiction: str | None
norm_type: str | None
norm_number: str | None
norm_year: str | None
article: str | None
paragraph: str | None
inciso: str | None
alinea: str | None
text: str
source_url: str | None
version: str
content_hash: str
created_at: datetime
metadata: dict
```

### LegalCitation

Campos mínimos:

```text
citation_id: str
source: str
doc_type: str
title: str
source_url: str | None
article: str | None
case_number: str | None
court: str | None
judgment_date: date | None
publication_date: date | None
support_level: str
chunk_id: str | None
```

### CaseLawDocument

Campos mínimos:

```text
document_id: str
doc_type: "case_law"
source: str
court: str
case_number: str | None
rapporteur: str | None
panel: str | None
judgment_date: date | None
publication_date: date | None
legal_area: str | None
precedent_type: str | None
is_binding: bool
ementa: str | None
full_text: str | None
source_url: str | None
content_hash: str
metadata: dict
```

---

## 9. Metadata obrigatória para RAG jurídico

### Legislação

Payload para vector DB:

```json
{
  "doc_type": "statute",
  "source": "planalto",
  "legal_area": "consumer",
  "country": "BR",
  "jurisdiction": "federal",
  "norm_type": "lei",
  "norm_number": "8078",
  "norm_year": "1990",
  "article": "12",
  "is_current": true,
  "version": "2026-06-16",
  "source_url": "...",
  "content_hash": "sha256:..."
}
```

### Jurisprudência

Payload para vector DB:

```json
{
  "doc_type": "case_law",
  "source": "stj",
  "court": "STJ",
  "case_number": "...",
  "rapporteur": "...",
  "panel": "...",
  "judgment_date": "...",
  "publication_date": "...",
  "legal_area": "consumer",
  "precedent_type": "acordao",
  "is_binding": false,
  "source_url": "...",
  "content_hash": "sha256:..."
}
```

---

## 10. Orquestradores do projeto

Existem dois tipos de orquestradores:

1. **Orquestrador de implementação**: coordena coding agents em paralelo.
2. **Orquestrador runtime**: coordena agentes de IA dentro do produto.

---

# PARTE A — Orquestração da implementação

## 11. Orquestrador de implementação

### Papel

O `ImplementationOrchestrator` coordena agentes paralelos, define ownership de arquivos, valida contratos e integra entregas.

### Responsabilidades

- Ler este prompt antes de qualquer implementação.
- Dividir o trabalho em fases.
- Criar issues/tarefas por módulo.
- Garantir que cada agente trabalhe em arquivos sem conflito.
- Validar contratos entre módulos.
- Rodar testes, lint e type check após cada fase.
- Atualizar README e docs progressivamente.
- Não avançar de fase sem cumprir critérios de aceite.

### Protocolo de execução

Para cada fase:

```text
1. Confirmar objetivo da fase.
2. Listar arquivos que serão criados/alterados.
3. Distribuir tarefas por agente.
4. Implementar em paralelo quando possível.
5. Integrar mudanças.
6. Rodar testes.
7. Atualizar documentação.
8. Registrar pendências.
9. Gerar resumo da fase.
```

### Estratégia com Git worktrees

Usar worktrees para agentes em paralelo:

```bash
git worktree add ../jus-rag-foundation -b feat/foundation
git worktree add ../jus-rag-ingestion -b feat/ingestion
git worktree add ../jus-rag-rag -b feat/rag-core
git worktree add ../jus-rag-answer -b feat/answer-audit
git worktree add ../jus-rag-evals -b feat/evals
git worktree add ../jus-rag-ui -b feat/ui
```

### Convenção de branches

```text
main
feat/foundation
feat/legal-schemas
feat/ingestion-cdc
feat/vector-search
feat/ask-api
feat/citation-auditor
feat/stj-loader
feat/langgraph-orchestration
feat/evals
feat/demo-ui
release/v1.0
```

### Convenção de commits

Usar Conventional Commits:

```text
feat: add FastAPI health endpoint
feat: add legal schemas
feat: implement CDC article chunker
feat: add Qdrant vector store
fix: handle empty retrieval results
refactor: isolate answer writer from API route
test: add citation auditor tests
docs: document legal limitations
```

---

## 12. Agentes paralelos de implementação

### 12.1 FoundationAgent

Ownership principal:

```text
pyproject.toml
Makefile
docker-compose.yml
.env.example
apps/api/main.py
apps/api/dependencies.py
apps/api/routes/health.py
packages/config/settings.py
tests/integration/test_health.py
README.md inicial
```

Missão:

```text
Criar base executável do projeto com FastAPI, Docker, settings, healthcheck, lint e testes.
```

Critérios:

```text
make up funciona
GET /health retorna status ok
make test passa
```

---

### 12.2 LegalSchemaAgent

Ownership principal:

```text
packages/legal_types/schemas.py
packages/legal_types/enums.py
packages/legal_types/citations.py
packages/legal_types/hierarchy.py
packages/legal_types/temporal_validity.py
tests/unit/legal_types/
```

Missão:

```text
Definir modelos jurídicos tipados, enums e utilitários para citações, hierarquia normativa e vigência.
```

Critérios:

```text
Schemas validam dados mínimos
Enums cobrem statute, case_law, precedent, doctrine, unknown
Testes cobrem criação de chunks e citações
```

---

### 12.3 IngestionAgent

Ownership principal:

```text
packages/ingestion/
apps/worker/jobs/ingest_cdc.py
data/seed/cdc/cdc.md
data/generated/.gitkeep
tests/unit/ingestion/
```

Missão:

```text
Criar pipeline de ingestão local do CDC com chunking por artigo e geração de JSONL estruturado.
```

Critérios:

```text
make ingest-cdc gera data/generated/cdc_chunks.jsonl
Artigos 6º, 12, 14, 18, 26 e 49 são detectados
Chunks têm hash e metadata jurídica
```

---

### 12.4 StorageAgent

Ownership principal:

```text
packages/storage/postgres.py
packages/storage/qdrant.py
packages/storage/repositories.py
apps/worker/jobs/index_cdc.py
tests/unit/storage/
tests/integration/storage/
```

Missão:

```text
Criar adaptadores para Postgres e Qdrant, com indexação dos chunks jurídicos.
```

Critérios:

```text
Collection legal_chunks é criada
Chunks são indexados no Qdrant
Indexação é idempotente
Testes usam fake provider ou mocks
```

---

### 12.5 EmbeddingAgent

Ownership principal:

```text
packages/embeddings/base.py
packages/embeddings/openai_provider.py
packages/embeddings/fake_provider.py
tests/unit/embeddings/
```

Missão:

```text
Criar interface de embeddings e providers real/fake.
```

Critérios:

```text
Provider fake permite testes sem API externa
Provider OpenAI lê config do .env
Interface aceita lista de textos e retorna lista de vetores
```

---

### 12.6 RAGAgent

Ownership principal:

```text
packages/rag/query_analyzer.py
packages/rag/retriever.py
packages/rag/hybrid_retriever.py
packages/rag/reranker.py
packages/rag/legal_ranker.py
packages/rag/context_builder.py
apps/api/routes/search.py
apps/worker/jobs/search_demo.py
tests/unit/rag/
tests/integration/test_search.py
```

Missão:

```text
Implementar retrieval jurídico com filtros, ranking e montagem de contexto.
```

Critérios:

```text
POST /search retorna chunks com score e citation metadata
Busca por defeito do produto retorna CDC art. 12 nos dados seed
Busca por arrependimento retorna CDC art. 49 nos dados seed
```

---

### 12.7 AnswerAgent

Ownership principal:

```text
packages/answer/prompts.py
packages/answer/schemas.py
packages/answer/formatter.py
packages/answer/answer_writer.py
apps/api/routes/ask.py
apps/worker/jobs/ask_demo.py
tests/unit/answer/
tests/integration/test_ask.py
```

Missão:

```text
Criar resposta jurídica estruturada com fontes obrigatórias, caveats e recusa segura.
```

Critérios:

```text
POST /ask retorna short_answer, legal_basis, caveats, sources, not_legal_advice
Resposta sem fonte suficiente recusa
Resposta não inventa artigos fora do contexto
```

---

### 12.8 CitationAuditAgent

Ownership principal:

```text
packages/answer/citation_auditor.py
packages/agents/citation_auditor.py
tests/unit/answer/test_citation_auditor.py
tests/evals/test_unsupported_claims.py
```

Missão:

```text
Auditar claims jurídicos e impedir resposta sem suporte suficiente.
```

Critérios:

```text
Claims sem fonte são detectados
citation_coverage é calculado
unsupported_legal_claim_rate é calculado
Resposta final remove ou qualifica afirmações sem suporte
```

---

### 12.9 CaseLawAgent

Ownership principal:

```text
packages/ingestion/loaders/stj.py
packages/ingestion/loaders/stf.py
packages/legal_types/schemas.py, apenas extensão coordenada
packages/rag/retriever.py, apenas extensão coordenada
tests/unit/ingestion/test_stj_loader.py
```

Missão:

```text
Adicionar base para jurisprudência, começando com loader local/STJ seed antes de integração externa real.
```

Critérios:

```text
Jurisprudência seed é normalizada
Busca separa statute de case_law
Resposta tem bloco de jurisprudência quando disponível
```

---

### 12.10 LangGraphAgent

Ownership principal:

```text
packages/agents/state.py
packages/agents/graph.py
packages/agents/intake.py
packages/agents/classify_area.py
packages/agents/statute_researcher.py
packages/agents/case_law_researcher.py
packages/agents/precedent_analyzer.py
packages/agents/answer_writer.py
packages/agents/citation_auditor.py
packages/agents/risk_checker.py
tests/unit/agents/
```

Missão:

```text
Transformar o pipeline RAG em workflow agentic com estado e etapas auditáveis.
```

Critérios:

```text
Grafo executa intake → classify → retrieve → answer → audit → risk → final
Estado final contém resposta, fontes, auditoria e riscos
Cada etapa gera trace simples
```

---

### 12.11 EvalAgent

Ownership principal:

```text
packages/evals/
data/seed/questions/
tests/evals/
```

Missão:

```text
Criar avaliação de retrieval, citações e fidelidade.
```

Critérios:

```text
make eval executa
Relatório JSON/Markdown é gerado
Pelo menos 30 perguntas golden na v1
Métricas incluem recall@k, citation_coverage, unsupported_legal_claim_rate
```

---

### 12.12 UIAgent

Ownership principal:

```text
apps/web/
docs/demo-script.md
README.md, apenas seção de demo coordenada
```

Missão:

```text
Criar demo visual simples para GitHub.
```

Critérios:

```text
Usuário faz pergunta
UI mostra resposta, fontes e ressalvas
UI mostra chunks/fonte usados
UI mostra aviso de não aconselhamento jurídico
```

---

### 12.13 DocsAgent

Ownership principal:

```text
README.md
docs/
```

Missão:

```text
Documentar arquitetura, limitações, fontes, evals, governança e uso local.
```

Critérios:

```text
README permite rodar o projeto do zero
Docs explicam Legal RAG, fonte oficial, limitações e roadmap
```

---

# PARTE B — Orquestração runtime do produto

## 13. Estado do workflow agentic

Implementar em `packages/agents/state.py`.

Estado alvo:

```python
from typing import Any, Literal
from pydantic import BaseModel, Field

class RetrievedSource(BaseModel):
    chunk_id: str
    doc_type: str
    title: str
    text: str
    score: float
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class CitationAuditResult(BaseModel):
    citation_coverage: float
    unsupported_claim_rate: float
    unsupported_claims: list[str] = Field(default_factory=list)
    passed: bool

class LegalResearchState(BaseModel):
    run_id: str
    question: str
    jurisdiction: str = "BR"
    legal_area: str | None = None
    facts: dict[str, Any] = Field(default_factory=dict)
    missing_facts: list[str] = Field(default_factory=list)
    retrieved_statutes: list[RetrievedSource] = Field(default_factory=list)
    retrieved_case_law: list[RetrievedSource] = Field(default_factory=list)
    selected_context: list[RetrievedSource] = Field(default_factory=list)
    draft_answer: str | None = None
    final_answer: str | None = None
    caveats: list[str] = Field(default_factory=list)
    audit: CitationAuditResult | None = None
    status: Literal["running", "needs_more_info", "answered", "refused", "failed"] = "running"
    errors: list[str] = Field(default_factory=list)
```

---

## 14. Grafo LangGraph alvo

Implementar em `packages/agents/graph.py`.

Fluxo:

```text
START
  → intake
  → classify_legal_area
  → retrieve_statutes
  → retrieve_case_law
  → rerank_and_select_context
  → synthesize_answer
  → audit_citations
  → check_risks
  → final_answer
  → END
```

Regras de roteamento:

```text
- Se a pergunta estiver fora do escopo e não houver fonte: ir para refusal.
- Se missing_facts for crítico: responder com necessidade de mais contexto.
- Se citation audit falhar: voltar para synthesize_answer uma vez.
- Se falhar duas vezes: responder com versão conservadora ou recusa.
```

---

## 15. Agentes jurídicos runtime

### 15.1 IntakeAgent

Função:

```text
Extrair pergunta jurídica, fatos relevantes, jurisdição, datas, área provável e lacunas.
```

Entrada:

```text
question
```

Saída:

```text
facts
missing_facts
jurisdiction
legal_area provável
```

Prompt base:

```text
Você é um agente de triagem jurídica para um sistema de pesquisa, não para aconselhamento definitivo.
Extraia da pergunta: área provável, fatos, datas, jurisdição, pedido do usuário e lacunas.
Não responda ao mérito. Não invente fatos.
Se faltarem dados importantes, liste-os em missing_facts.
```

---

### 15.2 LegalAreaClassifier

Função:

```text
Classificar área jurídica e decidir quais retrievers usar.
```

Áreas iniciais:

```text
consumer
civil
labor
constitutional
tax
criminal
administrative
unknown
```

Regra MVP:

```text
Se não for consumer, responder que a base atual cobre principalmente direito do consumidor, mas ainda pode pesquisar fontes genéricas se disponíveis.
```

---

### 15.3 StatuteResearchAgent

Função:

```text
Buscar legislação aplicável.
```

Regras:

```text
- Priorizar legislação vigente.
- Usar filtros por legal_area e doc_type=statute.
- Preservar artigo, lei e URL.
- Retornar também score e justificativa curta.
```

---

### 15.4 CaseLawResearchAgent

Função:

```text
Buscar jurisprudência relevante.
```

Regras:

```text
- Priorizar STJ/STF quando houver.
- Separar acórdão comum de precedente vinculante.
- Não tratar qualquer decisão como tese vinculante.
- Preservar tribunal, processo, relator, data e URL.
```

---

### 15.5 PrecedentAnalyzerAgent

Função:

```text
Identificar autoridade do precedente.
```

Classificações:

```text
binding_precedent
repetitive_appeal
general_repercussion
binding_summary
summary
ordinary_case_law
unknown
```

---

### 15.6 AnswerWriterAgent

Função:

```text
Redigir resposta com base apenas no contexto selecionado.
```

Formato obrigatório:

```text
Resposta curta
Fundamento legal
Jurisprudência relevante, se houver
Ressalvas
Fontes consultadas
Aviso de limitação
```

Prompt base:

```text
Você é um redator jurídico assistivo. Responda em português brasileiro, de forma clara e técnica.
Use exclusivamente as fontes fornecidas no contexto.
Não invente artigos, súmulas, decisões, teses ou números de processo.
Toda afirmação jurídica relevante deve apontar para uma fonte.
Se o contexto não sustentar uma conclusão, diga que não há base suficiente.
Não forneça aconselhamento jurídico definitivo.
```

---

### 15.7 CitationAuditorAgent

Função:

```text
Auditar se a resposta está suportada pelas fontes.
```

Verificações:

```text
- Claims jurídicos possuem fonte?
- Fonte citada existe no contexto?
- Artigo citado corresponde ao chunk?
- A resposta extrapola o texto recuperado?
- Há linguagem absoluta indevida?
```

Saída:

```text
citation_coverage
unsupported_claim_rate
unsupported_claims
passed
```

---

### 15.8 RiskCheckerAgent

Função:

```text
Adicionar ressalvas, limites e necessidade de advogado quando apropriado.
```

Regras:

```text
- Se depender de prova, fato ou documento: avisar.
- Se houver lacuna de fonte: avisar.
- Se estiver fora do escopo: avisar.
- Evitar tom de certeza absoluta.
```

---

# PARTE C — Fases do projeto

## 16. Fase 0 — Planejamento e documentação inicial

Versão: `v0.0`

### Objetivo

Definir escopo, arquitetura, fonte de dados, riscos e critérios de sucesso.

### Tarefas

```text
- Criar README.md inicial.
- Criar docs/architecture.md.
- Criar docs/source-policy.md.
- Criar docs/limitations.md.
- Criar docs/evaluation.md.
- Criar docs/governance.md.
- Definir roadmap.md.
```

### Critérios de aceite

```text
- Escopo inicial definido como direito do consumidor.
- Projeto deixa claro que não presta aconselhamento jurídico.
- Arquitetura RAG está desenhada.
- Fontes e limitações estão documentadas.
```

### Agentes paralelos

```text
DocsAgent
ImplementationOrchestrator
```

---

## 17. Fase 1 — Bootstrap técnico

Versão: `v0.1`

### Objetivo

Criar base executável do projeto.

### Tarefas

```text
- Criar pyproject.toml.
- Configurar FastAPI.
- Criar GET /health.
- Criar Docker Compose com api, postgres, qdrant e redis.
- Criar .env.example.
- Criar Makefile.
- Criar settings.py com pydantic-settings.
- Criar testes de healthcheck.
- Configurar ruff e mypy.
```

### Critérios de aceite

```text
make up funciona
GET /health retorna {"status": "ok"}
make test passa
make lint passa ou está documentado se mypy ainda estiver parcial
```

### Agentes paralelos

```text
FoundationAgent
DocsAgent
```

---

## 18. Fase 2 — Modelos jurídicos e ingestão do CDC

Versão: `v0.2`

### Objetivo

Ingerir o Código de Defesa do Consumidor como fonte seed.

### Tarefas

```text
- Criar LegalDocument.
- Criar LegalChunk.
- Criar LegalCitation.
- Criar SourceMetadata.
- Criar enums jurídicos.
- Criar LocalMarkdownLoader.
- Criar LegalChunker por artigo.
- Criar versionamento por content_hash.
- Criar data/seed/cdc/cdc.md com artigos 6º, 12, 14, 18, 26 e 49.
- Criar script apps.worker.jobs.ingest_cdc.
- Gerar data/generated/cdc_chunks.jsonl.
- Criar testes unitários do chunker.
```

### Critérios de aceite

```text
make ingest-cdc gera JSONL
Artigos seed são detectados
Chunks preservam artigo, lei, fonte, versão e hash
Reingestão é idempotente no nível de hash
```

### Agentes paralelos

```text
LegalSchemaAgent
IngestionAgent
DocsAgent
```

---

## 19. Fase 3 — Embeddings e Qdrant

Versão: `v0.3`

### Objetivo

Indexar chunks jurídicos em vector DB e buscar semanticamente.

### Tarefas

```text
- Criar EmbeddingProvider.
- Criar FakeEmbeddingProvider para testes.
- Criar OpenAIEmbeddingProvider.
- Criar QdrantVectorStore.
- Criar collection legal_chunks.
- Criar job index_cdc.
- Criar POST /search.
- Criar search_demo.
- Criar testes com mocks.
```

### Critérios de aceite

```text
make index-cdc indexa chunks
POST /search retorna top_k chunks com metadata
Pergunta sobre defeito do produto retorna art. 12
Pergunta sobre arrependimento retorna art. 49
```

### Agentes paralelos

```text
EmbeddingAgent
StorageAgent
RAGAgent
```

---

## 20. Fase 4 — API /ask com resposta citada

Versão: `v0.4`

### Objetivo

Responder perguntas jurídicas com base nos chunks recuperados.

### Tarefas

```text
- Criar LLMProvider e FakeLLMProvider.
- Criar AnswerRequest e AnswerResponse.
- Criar ContextBuilder.
- Criar AnswerWriter.
- Criar prompts jurídicos.
- Criar POST /ask.
- Criar ask_demo.
- Criar recusa segura.
```

### Critérios de aceite

```text
POST /ask retorna resposta estruturada
Toda resposta tem sources
Perguntas sem fonte retornam recusa segura
Resposta inclui not_legal_advice=true
```

### Agentes paralelos

```text
AnswerAgent
RAGAgent
DocsAgent
```

---

## 21. Fase 5 — Auditor de citações

Versão: `v0.5`

### Objetivo

Reduzir alucinação e claims sem suporte.

### Tarefas

```text
- Criar CitationAuditor.
- Criar extração simples de claims.
- Verificar claims contra contexto.
- Calcular citation_coverage.
- Calcular unsupported_legal_claim_rate.
- Reescrever resposta conservadora quando necessário.
- Salvar audit no run result.
```

### Critérios de aceite

```text
Claims sem suporte são detectados
Resposta final remove afirmações sem suporte
Testes cobrem casos de alucinação simulada
```

### Agentes paralelos

```text
CitationAuditAgent
AnswerAgent
EvalAgent
```

---

## 22. Fase 6 — Jurisprudência STJ seed

Versão: `v0.6`

### Objetivo

Adicionar suporte inicial para jurisprudência.

### Tarefas

```text
- Criar CaseLawDocument.
- Criar loader local de jurisprudência seed.
- Criar data/seed/case_law/stj_consumer_seed.jsonl.
- Criar chunker de ementa.
- Indexar case_law_chunks ou mesma collection com doc_type=case_law.
- Atualizar retriever para doc_type=case_law.
- Atualizar resposta para bloco Jurisprudência relevante.
```

### Critérios de aceite

```text
Busca separa legislação e jurisprudência
Resposta mostra fundamento legal e jurisprudência separadamente
Jurisprudência sem fonte não é exibida
```

### Agentes paralelos

```text
CaseLawAgent
RAGAgent
AnswerAgent
```

---

## 23. Fase 7 — Orquestração LangGraph

Versão: `v0.7`

### Objetivo

Transformar pipeline em workflow agentic.

### Tarefas

```text
- Criar LegalResearchState.
- Criar graph.py.
- Implementar IntakeAgent.
- Implementar LegalAreaClassifier.
- Implementar StatuteResearchAgent.
- Implementar CaseLawResearchAgent.
- Implementar AnswerWriterAgent.
- Implementar CitationAuditorAgent.
- Implementar RiskCheckerAgent.
- Adicionar traces por etapa.
```

### Critérios de aceite

```text
Grafo roda de ponta a ponta
Estado final contém resposta, fontes, auditoria e caveats
Falha de audit gera revisão ou recusa
```

### Agentes paralelos

```text
LangGraphAgent
CitationAuditAgent
AnswerAgent
ObservabilityAgent, se criado
```

---

## 24. Fase 8 — Evals

Versão: `v0.8`

### Objetivo

Medir qualidade do retrieval e das respostas.

### Tarefas

```text
- Criar golden_questions.yaml.
- Criar 30 perguntas de direito do consumidor.
- Criar retrieval_eval.py.
- Criar citation_eval.py.
- Criar answer_eval.py.
- Criar run_all.py.
- Gerar relatório JSON e Markdown.
- Integrar make eval.
```

### Métricas obrigatórias

```text
retrieval_recall_at_5
retrieval_precision_at_5
citation_coverage
citation_accuracy
unsupported_legal_claim_rate
refusal_when_no_source_rate
answer_relevancy, opcional
faithfulness, opcional
```

### Critérios de aceite

```text
make eval executa
Relatório é gerado
Build pode falhar se unsupported_legal_claim_rate exceder threshold
```

### Agentes paralelos

```text
EvalAgent
RAGAgent
CitationAuditAgent
```

---

## 25. Fase 9 — UI demo

Versão: `v0.9`

### Objetivo

Criar uma interface simples para demonstração no GitHub.

### Tarefas

```text
- Criar app Streamlit ou UI simples.
- Campo de pergunta.
- Exibir resposta.
- Exibir fontes em cards.
- Exibir chunks usados.
- Exibir caveats.
- Exibir audit score.
- Exibir aviso de não aconselhamento jurídico.
```

### Critérios de aceite

```text
Demo local funciona
README tem instruções de uso
Docs têm roteiro de demo
```

### Agentes paralelos

```text
UIAgent
DocsAgent
```

---

## 26. Fase 10 — v1.0

Versão: `v1.0`

### Objetivo

Consolidar release estável e demonstrável.

### Entregáveis

```text
- API funcionando.
- Docker Compose completo.
- CDC ingerido.
- Jurisprudência seed/STJ inicial.
- Qdrant vector search.
- Resposta com citações.
- Auditor de citações.
- Workflow LangGraph.
- Evals.
- UI demo.
- Documentação completa.
- CI GitHub Actions.
- Release tag v1.0.
```

### Critérios de aceite v1

```text
make up funciona
make ingest-cdc funciona
make index-cdc funciona
make ask-demo funciona
make eval funciona
README permite rodar do zero
Sistema responde com citações
Sistema recusa quando não encontra base
Evals rodam automaticamente
Arquitetura está documentada
```

---

# PARTE D — Contratos técnicos entre módulos

## 27. Contrato de EmbeddingProvider

```python
from typing import Protocol

class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, query: str) -> list[float]:
        ...
```

Regras:

```text
- Não chamar provider real em testes unitários.
- Fake provider deve ser determinístico.
- Erros de API externa devem ser tratados com mensagem clara.
```

---

## 28. Contrato de VectorStore

```python
from typing import Protocol, Any

class VectorStore(Protocol):
    def upsert_chunks(self, chunks: list[Any], vectors: list[list[float]]) -> None:
        ...

    def search(
        self,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[Any]:
        ...
```

Regras:

```text
- VectorStore não conhece FastAPI.
- VectorStore não chama LLM.
- VectorStore retorna objetos com score e metadata.
```

---

## 29. Contrato de Retriever

Entrada:

```json
{
  "query": "O fornecedor responde por defeito do produto?",
  "legal_area": "consumer",
  "doc_type": "statute",
  "top_k": 8
}
```

Saída:

```json
[
  {
    "chunk_id": "cdc-8078-1990-art-12",
    "text": "...",
    "score": 0.92,
    "citation": {
      "title": "Código de Defesa do Consumidor",
      "article": "12",
      "source_url": "..."
    },
    "metadata": {}
  }
]
```

---

## 30. Contrato de AnswerWriter

Entrada:

```text
question
selected_context
answer_style
```

Saída:

```json
{
  "short_answer": "...",
  "legal_basis": [
    {
      "text": "...",
      "citations": ["cdc-8078-1990-art-12"]
    }
  ],
  "case_law": [],
  "caveats": [],
  "sources": [],
  "not_legal_advice": true
}
```

---

## 31. Contrato de CitationAuditor

Entrada:

```text
answer
selected_context
sources
```

Saída:

```json
{
  "citation_coverage": 0.92,
  "unsupported_legal_claim_rate": 0.04,
  "unsupported_claims": [],
  "passed": true
}
```

---

# PARTE E — Prompts internos do produto

## 32. Prompt do AnswerWriter

```text
Você é um redator jurídico assistivo para um sistema de pesquisa jurídica brasileira.

Responda em português brasileiro.
Use exclusivamente as fontes fornecidas no CONTEXTO.
Não invente artigos, leis, súmulas, decisões, teses ou números de processo.
Toda afirmação jurídica relevante deve estar apoiada em uma fonte do contexto.
Se o contexto não sustentar uma conclusão, diga que não há base suficiente.
Não forneça aconselhamento jurídico definitivo.
Use linguagem clara, técnica e conservadora.

Formato obrigatório:
1. Resposta curta
2. Fundamento legal
3. Jurisprudência relevante, se houver
4. Ressalvas e limites
5. Fontes consultadas
6. Aviso: esta resposta é informativa e não substitui análise de advogado.
```

---

## 33. Prompt do CitationAuditor

```text
Você é um auditor de citações jurídicas.

Sua tarefa é verificar se a resposta está totalmente suportada pelas fontes recuperadas.

Verifique:
- Toda afirmação jurídica relevante tem fonte?
- A fonte citada existe no contexto?
- O artigo citado corresponde ao conteúdo?
- A resposta extrapola a fonte?
- Há linguagem absoluta indevida?
- A resposta inventa jurisprudência, súmula, tese ou número de processo?

Retorne:
- claims suportados
- claims sem suporte
- citation_coverage
- unsupported_legal_claim_rate
- passed true/false

Se houver claim sem suporte, recomende remover ou qualificar a afirmação.
```

---

## 34. Prompt do RiskChecker

```text
Você é um agente de risco e limitação jurídica.

Revise a resposta final para garantir que:
- Não pareça aconselhamento jurídico definitivo.
- Indique quando faltam fatos relevantes.
- Indique quando a conclusão depende de prova, documentos ou contexto.
- Indique que a resposta é informativa.
- Evite termos absolutos como "sempre", "nunca", "garantido", exceto quando a fonte sustentar claramente.
```

---

# PARTE F — Evals e qualidade

## 35. Dataset golden inicial

Criar `data/seed/questions/consumer_golden.yaml`:

```yaml
- id: consumer_001
  question: "O fornecedor responde objetivamente por defeito do produto?"
  expected_sources:
    - "Lei 8.078/1990 art. 12"
  expected_terms:
    - "responsabilidade objetiva"
    - "defeito do produto"
    - "nexo causal"
  forbidden_terms:
    - "responsabilidade subjetiva como regra"

- id: consumer_002
  question: "Qual é o prazo de arrependimento em compra pela internet?"
  expected_sources:
    - "Lei 8.078/1990 art. 49"
  expected_terms:
    - "sete dias"
    - "fora do estabelecimento comercial"

- id: consumer_003
  question: "Quais são direitos básicos do consumidor?"
  expected_sources:
    - "Lei 8.078/1990 art. 6º"
  expected_terms:
    - "direitos básicos"
    - "informação"
```

Na v1, expandir para pelo menos 30 perguntas.

---

## 36. Critérios de qualidade v1

```text
retrieval_recall_at_5 >= 0.80
citation_coverage >= 0.90
unsupported_legal_claim_rate <= 0.05
refusal_when_no_source_rate >= 0.90 para perguntas fora do escopo seed
make test passa
make eval passa
```

---

## 37. Testes obrigatórios

### Unitários

```text
- Legal schemas.
- Chunker por artigo.
- Hash/versioning.
- Fake embeddings.
- Retriever com mocks.
- Answer formatter.
- Citation auditor.
- Legal ranker.
```

### Integração

```text
- /health.
- /search com dados seed.
- /ask com dados seed.
- indexação Qdrant local.
```

### Evals

```text
- Retrieval recall.
- Citation coverage.
- Unsupported claims.
- Recusa segura.
```

---

# PARTE G — Ranking jurídico

## 38. Scoring composto

Implementar gradualmente:

```text
final_score =
  0.30 * semantic_similarity
+ 0.20 * bm25_score
+ 0.15 * legal_authority
+ 0.10 * binding_weight
+ 0.10 * recency
+ 0.10 * exact_citation_match
+ 0.05 * source_quality
```

No MVP, se BM25 ainda não existir:

```text
final_score =
  0.70 * semantic_similarity
+ 0.20 * legal_authority
+ 0.10 * exact_citation_match
```

---

## 39. Pesos de autoridade

```text
Constituição Federal: 1.00
Lei federal vigente: 0.95
Súmula vinculante: 0.95
STF repercussão geral: 0.95
STJ recurso repetitivo: 0.90
STJ súmula: 0.88
STJ acórdão comum: 0.75
TJ estadual: 0.60
Doutrina: 0.40
Blog/artigo: 0.20
Fonte desconhecida: 0.10
```

---

# PARTE H — Segurança, governança e limitações

## 40. Regras de segurança

```text
- Não ingerir dados pessoais reais no seed.
- Não usar processos sigilosos.
- Não armazenar perguntas sensíveis sem opção de anonimização.
- Não expor stack traces ao usuário final.
- Não commitar API keys.
- Não prometer aconselhamento jurídico.
- Não permitir resposta sem fonte em temas jurídicos.
```

---

## 41. Texto de limitação padrão

```text
Esta resposta tem finalidade informativa e foi gerada com base nas fontes recuperadas pelo sistema. Ela não substitui a análise de um advogado ou profissional habilitado, especialmente porque a conclusão pode depender de fatos, documentos, datas e jurisprudência atualizada.
```

---

# PARTE I — Prompts de execução por fase

## 42. Prompt para iniciar o projeto inteiro

```text
Você recebeu o Prompt Master do projeto `jus-rag-brasil`.

Execute a Fase 1 e prepare a base para as fases seguintes.

Antes de codar:
1. Liste os arquivos que serão criados.
2. Confirme os contratos principais.
3. Separe o que é implementação real e o que será stub.

Depois:
1. Implemente.
2. Rode testes.
3. Atualize README.
4. Entregue resumo com comandos validados.

Não implemente RAG ainda na Fase 1.
```

---

## 43. Prompt para Fase 1

```text
Implemente a Fase 1 do `jus-rag-brasil`: bootstrap técnico.

Requisitos:
- Python 3.12+.
- FastAPI.
- GET /health retornando {"status": "ok"}.
- pyproject.toml com dependências principais.
- Docker Compose com api, postgres, qdrant e redis.
- .env.example.
- Makefile com up, down, test, lint, format.
- settings.py com pydantic-settings.
- Teste automatizado para /health.
- README inicial com objetivo e aviso de não aconselhamento jurídico.

Critérios de aceite:
- make up sobe serviços.
- make test passa.
- GET /health funciona.
```

---

## 44. Prompt para Fase 2

```text
Implemente a Fase 2 do `jus-rag-brasil`: modelos jurídicos e ingestão do CDC.

Requisitos:
- Criar LegalDocument, LegalChunk, LegalCitation e SourceMetadata.
- Criar enums jurídicos.
- Criar LocalMarkdownLoader.
- Criar LegalChunker por artigo.
- Criar seed data/seed/cdc/cdc.md com arts. 6º, 12, 14, 18, 26 e 49.
- Criar script python -m apps.worker.jobs.ingest_cdc.
- Gerar data/generated/cdc_chunks.jsonl.
- Criar testes do chunker.

Critérios:
- make ingest-cdc gera JSONL.
- Artigos são detectados corretamente.
- Chunks preservam metadata jurídica.
- make test passa.
```

---

## 45. Prompt para Fase 3

```text
Implemente a Fase 3 do `jus-rag-brasil`: embeddings e busca vetorial.

Requisitos:
- Criar EmbeddingProvider.
- Criar FakeEmbeddingProvider para testes.
- Criar OpenAIEmbeddingProvider.
- Criar QdrantVectorStore.
- Criar collection legal_chunks.
- Criar job index_cdc.
- Criar POST /search.
- Criar search_demo.

Critérios:
- make index-cdc indexa chunks.
- POST /search retorna chunks com metadata.
- Busca por defeito do produto retorna art. 12 nos dados seed.
- Busca por arrependimento retorna art. 49 nos dados seed.
```

---

## 46. Prompt para Fase 4

```text
Implemente a Fase 4 do `jus-rag-brasil`: API /ask com resposta citada.

Requisitos:
- Criar LLMProvider e FakeLLMProvider.
- Criar AnswerRequest e AnswerResponse.
- Criar ContextBuilder.
- Criar AnswerWriter.
- Criar prompts jurídicos.
- Criar POST /ask.
- Criar ask_demo.
- Criar recusa segura.

Critérios:
- Toda resposta tem sources.
- Pergunta sem fonte suficiente recusa.
- Resposta inclui aviso de não aconselhamento jurídico.
```

---

## 47. Prompt para Fase 5

```text
Implemente a Fase 5 do `jus-rag-brasil`: auditor de citações.

Requisitos:
- Criar CitationAuditor.
- Extrair claims jurídicos simples.
- Verificar suporte contra selected_context.
- Calcular citation_coverage.
- Calcular unsupported_legal_claim_rate.
- Reescrever/remover claims sem suporte.
- Criar testes com respostas alucinadas simuladas.

Critérios:
- Claims sem suporte são detectados.
- Resposta final fica conservadora.
- Testes passam.
```

---

## 48. Prompt para Fase 6

```text
Implemente a Fase 6 do `jus-rag-brasil`: jurisprudência STJ seed.

Requisitos:
- Criar CaseLawDocument.
- Criar loader local de jurisprudência.
- Criar seed STJ em JSONL.
- Criar chunking de ementa.
- Indexar jurisprudência com doc_type=case_law.
- Atualizar retriever.
- Atualizar resposta com seção Jurisprudência relevante.

Critérios:
- Busca diferencia statute e case_law.
- Resposta separa fundamento legal e jurisprudência.
```

---

## 49. Prompt para Fase 7

```text
Implemente a Fase 7 do `jus-rag-brasil`: orquestração LangGraph.

Requisitos:
- Criar LegalResearchState.
- Criar grafo com intake, classify, retrieve, answer, audit, risk e final.
- Cada nó deve ser testável separadamente.
- Adicionar trace por etapa.
- Integrar /ask ao grafo quando ENABLE_AGENT_GRAPH=true.

Critérios:
- Grafo executa de ponta a ponta.
- Estado final contém resposta, fontes, auditoria e caveats.
```

---

## 50. Prompt para Fase 8

```text
Implemente a Fase 8 do `jus-rag-brasil`: evals.

Requisitos:
- Criar 30 perguntas golden.
- Criar retrieval_eval.py.
- Criar citation_eval.py.
- Criar answer_eval.py.
- Criar run_all.py.
- Gerar relatório JSON e Markdown.
- Integrar make eval.

Critérios:
- make eval executa.
- Métricas principais são calculadas.
- Relatório é salvo em data/generated/eval_report.md e .json.
```

---

## 51. Prompt para Fase 9

```text
Implemente a Fase 9 do `jus-rag-brasil`: UI demo.

Requisitos:
- Criar UI simples com Streamlit ou alternativa leve.
- Campo de pergunta.
- Exibir resposta.
- Exibir fontes.
- Exibir caveats.
- Exibir auditoria de citações.
- Exibir aviso de limitação.

Critérios:
- UI roda localmente.
- README explica como usar.
```

---

## 52. Prompt para v1.0

```text
Prepare o release v1.0 do `jus-rag-brasil`.

Requisitos:
- Revisar README.
- Revisar docs.
- Garantir que make up, make ingest-cdc, make index-cdc, make ask-demo e make eval funcionam.
- Adicionar GitHub Actions.
- Adicionar exemplos de perguntas.
- Adicionar demo-script.md.
- Garantir que nenhum secret foi commitado.
- Criar changelog.
- Criar tag v1.0.

Critérios:
- Projeto pode ser executado por outra pessoa do zero.
- Documentação explica arquitetura e limitações.
- Evals rodam.
- Demo funciona.
```

---

# PARTE J — Ordem recomendada de execução paralela

## 53. Execução com agentes em paralelo

### Rodada 1

```text
FoundationAgent → Fase 1
DocsAgent → docs iniciais
ImplementationOrchestrator → valida estrutura
```

### Rodada 2

```text
LegalSchemaAgent → schemas e enums
IngestionAgent → loader/chunker CDC
DocsAgent → source-policy e legal-rag-design
```

### Rodada 3

```text
EmbeddingAgent → embeddings
StorageAgent → Qdrant
RAGAgent → /search
```

### Rodada 4

```text
AnswerAgent → /ask
CitationAuditAgent → auditor inicial
EvalAgent → primeiras perguntas golden
```

### Rodada 5

```text
CaseLawAgent → jurisprudência seed
RAGAgent → retrieval por doc_type
AnswerAgent → bloco jurisprudência
```

### Rodada 6

```text
LangGraphAgent → grafo agentic
CitationAuditAgent → integração audit node
EvalAgent → métricas completas
```

### Rodada 7

```text
UIAgent → demo
DocsAgent → README final
ImplementationOrchestrator → release v1
```

---

## 54. Política anti-conflito de arquivos

```text
- Cada agente deve respeitar ownership de arquivos.
- Alterações fora do ownership precisam ser documentadas antes.
- Schemas compartilhados devem ser alterados por LegalSchemaAgent ou via PR coordenado.
- README deve ser editado principalmente pelo DocsAgent.
- Rotas FastAPI podem ser criadas por agentes do módulo, mas main.py deve ser coordenado.
- Makefile deve ser coordenado pelo FoundationAgent ou ImplementationOrchestrator.
```

---

## 55. Definition of Done global

Uma tarefa só está concluída quando:

```text
- Código implementado.
- Testes relevantes criados.
- Testes passam.
- Lint não piora.
- Tipagem não piora.
- README/docs atualizados se necessário.
- Não há secrets.
- Não há chamadas externas em testes unitários.
- Comandos da fase funcionam.
- Critérios de aceite da fase foram cumpridos.
```

---

# PARTE K — Checklist de v1

## 56. Checklist técnico

```text
[ ] FastAPI funcionando
[ ] Docker Compose funcionando
[ ] Postgres configurado
[ ] Qdrant configurado
[ ] Redis configurado
[ ] CDC seed ingerido
[ ] Chunks jurídicos com metadata
[ ] Embeddings funcionando
[ ] Vector search funcionando
[ ] /search funcionando
[ ] /ask funcionando
[ ] Resposta com fontes
[ ] Recusa segura
[ ] Auditor de citações
[ ] Jurisprudência seed
[ ] LangGraph workflow
[ ] Evals
[ ] UI demo
[ ] README completo
[ ] Docs completas
[ ] CI configurado
```

## 57. Checklist jurídico/segurança

```text
[ ] Aviso de não aconselhamento jurídico
[ ] Não usa dados pessoais reais no seed
[ ] Não ingere processos sigilosos
[ ] Não responde sem fonte suficiente
[ ] Não inventa citações
[ ] Logs podem ser anonimizados
[ ] Limitações documentadas
[ ] Fonte, versão e hash preservados
```

---

# PARTE L — Resultado esperado da v1

Ao final da v1, uma pessoa deve conseguir rodar:

```bash
git clone <repo>
cd jus-rag-brasil
cp .env.example .env
make up
make ingest-cdc
make index-cdc
make ask-demo
make eval
```

E obter uma resposta como:

```text
Pergunta:
O fornecedor responde objetivamente por defeito do produto?

Resposta curta:
Em regra, sim. No CDC, a responsabilidade do fornecedor por defeito do produto é objetiva, desde que presentes defeito, dano e nexo causal, observadas as excludentes legais.

Fundamento legal:
- Código de Defesa do Consumidor, art. 12.

Ressalvas:
- A conclusão depende dos fatos concretos, da prova do dano e do nexo causal.
- Esta resposta é informativa e não substitui análise profissional.

Fontes:
- Lei 8.078/1990, art. 12.
```

---

# PARTE M — Primeira instrução para execução imediata

Use a instrução abaixo para começar agora:

```text
Comece a implementação do `jus-rag-brasil` seguindo este Prompt Master.

Execute somente a Fase 1 neste primeiro ciclo.

Antes de implementar:
- liste os arquivos que serão criados;
- confirme o escopo da Fase 1;
- diga quais partes serão stubs para fases futuras.

Depois implemente:
- pyproject.toml;
- FastAPI com /health;
- Docker Compose com api, postgres, qdrant e redis;
- .env.example;
- Makefile;
- settings.py;
- teste de healthcheck;
- README inicial.

Ao final:
- rode ou indique os comandos de teste;
- entregue resumo técnico;
- liste próximos passos da Fase 2.

Não implemente RAG ainda.
```

---

## 58. Observação final

Este projeto deve ser desenvolvido como produto técnico demonstrável, não como experimento solto.

O diferencial não é fazer a LLM “responder direito”. O diferencial é construir uma arquitetura que obriga a resposta jurídica a passar por:

```text
fonte → recuperação → ranking → síntese → auditoria → ressalva → avaliação
```

Essa é a linha central do `jus-rag-brasil`.
