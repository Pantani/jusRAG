# Roadmap

Entregas incrementais, fase a fase, com testes e critérios de aceite por etapa. **As Fases 1–9 estão concluídas; o projeto está em v1.0.**

| Fase | Versão | Status | Foco | Entregável principal |
|---|---|---|---|---|
| 0 | v0.0 | ✅ | Planejamento e documentação | README + docs (architecture, source-policy, limitations, evaluation, governance, roadmap). |
| 1 | v0.1 | ✅ | Bootstrap técnico | FastAPI + `GET /health`, Docker Compose (api/postgres/qdrant/redis), `.env.example`, Makefile, `settings.py`, ruff/mypy. |
| 2 | v0.2 | ✅ | Modelos jurídicos e ingestão do CDC | Schemas (`LegalDocument`, `LegalChunk`, `LegalCitation`, `SourceMetadata`), loader markdown, chunker por artigo, versionamento por hash, `make ingest-cdc`. |
| 3 | v0.3 | ✅ | Embeddings e Qdrant | `EmbeddingProvider` (+ fake), `QdrantVectorStore`, collection `legal_chunks`, `make index-cdc`, `POST /search`, `make search-demo`. |
| 4 | v0.4 | ✅ | `/ask` com resposta citada | `LLMProvider` (+ fake), `ContextBuilder`, `AnswerWriter`, prompts jurídicos, `POST /ask`, recusa segura, `make ask-demo`. |
| 5 | v0.5 | ✅ | Auditor de citações | `CitationAuditor`, extração e verificação de claims, `citation_coverage`, `unsupported_legal_claim_rate`, reescrita conservadora. |
| 6 | v0.6 | ✅ | Jurisprudência STJ seed | `CaseLawDocument`, loader de jurisprudência seed (súmulas 130/297/302/479/543), chunker de ementa, bloco separado de jurisprudência na resposta, `make ingest-case-law`. |
| 7 | v0.7 | ✅ | Orquestração LangGraph | `LegalResearchState`, `graph.py` (`run_graph`), agentes runtime (intake, classify, statute, case-law, answer, audit, risk), traces por etapa. |
| 8 | v0.8 | ✅ | Evals | Golden dataset (31 perguntas), retrieval/citation/answer evals, `run_all`, relatório JSON+MD, quality gate, `make eval`. |
| 9 | v0.9 | ✅ | UI demo | App Streamlit (`apps/web/app.py`): pergunta → resposta, fontes em cards, chunks usados, caveats, audit score, aviso de não aconselhamento. |
| 10 | v1.0 | 🚧 | Release estável | Consolidação: docs v1.0, README do zero. CI GitHub Actions e tag `v1.0` a cargo da release. |

## Critérios de aceite da v1.0

- `make up`, `make ingest-cdc`, `make ingest-case-law`, `make index-cdc`, `make ask-demo`, `make eval` funcionam.
- README permite rodar do zero (trilha offline com fakes + trilha com stack real).
- Sistema responde com citações e recusa com segurança quando não encontra base.
- Evals rodam automaticamente e impõem os quality gates (§36).
- Arquitetura, fontes e limitações documentadas.

## Pós-v1.0 (não-objetivos da v1)

Ingestão a partir das origens oficiais (loaders `planalto`/`lexml`/`stj`/`stf`), BM25/hybrid via OpenSearch, reranker dedicado, ranking jurídico completo (com binding/recency/source quality), expansão de áreas além de Direito do Consumidor. Ver [limitations.md](limitations.md).
