---
name: legal-rag-contracts
description: >-
  Contratos de integração do jus-rag-brasil — interfaces Protocol (EmbeddingProvider, VectorStore,
  Retriever, AnswerWriter, CitationAuditor), schemas de domínio jurídico (LegalDocument, LegalChunk,
  LegalCitation, CaseLawDocument), payloads de metadata para o vector DB, e o estado do grafo
  (LegalResearchState). Use ao criar/alterar qualquer fronteira entre módulos: schemas, providers de
  embeddings/LLM, vector store, retriever, /search, /ask, auditor, ou nós do LangGraph. Garante que o
  shape produzido por um módulo casa com o consumido por outro. A fonte normativa é o Prompt Master §8,9,13,27-31.
---

# Contratos de integração — jus-rag-brasil

Estes contratos são a espinha dorsal da integração. Um módulo que muda um shape sem atualizar este
contrato quebra os consumidores silenciosamente. Por isso: **schemas compartilhados só são alterados
pelo `legal-domain` agent**, e toda mudança de shape reflete em `_workspace/CONTRACTS.md`.

## Por que interfaces, não implementações concretas

Embeddings, vector store, reranker e LLM são pontos de variação (OpenAI hoje, outro provider amanhã;
Qdrant hoje, híbrido com OpenSearch depois) e de custo/rede em testes. Defini-los como `Protocol`
permite injetar `fake_provider` determinístico em unit tests (sem rede — regra §13) e trocar a
implementação real sem tocar nos consumidores. Implementações concretas **não conhecem FastAPI nem o
LLM**; retornam objetos com `score` + `metadata`.

## Interfaces (Protocols) — §27–28

```python
from typing import Protocol, Any

class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, query: str) -> list[float]: ...

class VectorStore(Protocol):
    def upsert_chunks(self, chunks: list[Any], vectors: list[list[float]]) -> None: ...
    def search(self, query_vector: list[float], top_k: int,
               filters: dict[str, Any] | None = None) -> list[Any]: ...
```

Regras: fake provider determinístico; erro de API externa tratado com mensagem clara (sem fallback
silencioso); `VectorStore.search` retorna objetos carregando `score` e `metadata`.

## Schemas de domínio — §8

Pydantic v2, em `packages/legal_types/schemas.py`. Campos mínimos (não reduzir):

- **LegalDocument**: `document_id, doc_type, source, title, legal_area|None, country, jurisdiction|None,
  norm_type|None, norm_number|None, norm_year|None, version, source_url|None, content_hash, created_at, metadata`
- **LegalChunk**: campos do documento + `chunk_id, article|None, paragraph|None, inciso|None, alinea|None, text`
- **LegalCitation**: `citation_id, source, doc_type, title, source_url|None, article|None, case_number|None,
  court|None, judgment_date|None, publication_date|None, support_level, chunk_id|None`
- **CaseLawDocument**: `document_id, doc_type="case_law", source, court, case_number|None, rapporteur|None,
  panel|None, judgment_date|None, publication_date|None, legal_area|None, precedent_type|None,
  is_binding, ementa|None, full_text|None, source_url|None, content_hash, metadata`

Enums (`enums.py`) cobrem ao menos: `doc_type ∈ {statute, case_law, precedent, doctrine, unknown}`;
`legal_area ∈ {consumer, civil, labor, constitutional, tax, criminal, administrative, unknown}`;
`precedent_type` (§15.5): `binding_precedent, repetitive_appeal, general_repercussion, binding_summary,
summary, ordinary_case_law, unknown`.

## Payloads de metadata no vector DB — §9

Legislação e jurisprudência têm payloads distintos; o retriever filtra por eles.

Statute: `{doc_type:"statute", source, legal_area, country:"BR", jurisdiction, norm_type, norm_number,
norm_year, article, is_current, version, source_url, content_hash}`

Case law: `{doc_type:"case_law", source, court, case_number, rapporteur, panel, judgment_date,
publication_date, legal_area, precedent_type, is_binding, source_url, content_hash}`

## Contrato do Retriever — §29

Entrada: `{query, legal_area, doc_type, top_k}`. Saída: lista de
`{chunk_id, text, score, citation:{title, article, source_url}, metadata}`.
Aceite seed: "defeito do produto" → CDC art. 12; "arrependimento" → CDC art. 49.

## Contrato do AnswerWriter — §30

Entrada: `question, selected_context, answer_style`. Saída:
```json
{"short_answer": "...", "legal_basis": [{"text": "...", "citations": ["cdc-8078-1990-art-12"]}],
 "case_law": [], "caveats": [], "sources": [], "not_legal_advice": true}
```
`not_legal_advice` é sempre `true`. Sem fonte suficiente → recusa segura (não preencher `legal_basis`
com conteúdo fora do `selected_context`).

## Contrato do CitationAuditor — §31

Entrada: `answer, selected_context, sources`. Saída:
`{citation_coverage: float, unsupported_legal_claim_rate: float, unsupported_claims: [...], passed: bool}`.

## Estado do grafo — LegalResearchState §13

Pydantic em `packages/agents/state.py`. Tipos auxiliares `RetrievedSource` e `CitationAuditResult`.
Campos: `run_id, question, jurisdiction="BR", legal_area|None, facts, missing_facts,
retrieved_statutes[], retrieved_case_law[], selected_context[], draft_answer|None, final_answer|None,
caveats[], audit|None, status, errors[]`, com
`status ∈ {running, needs_more_info, answered, refused, failed}`.

## Como validar integração

Ao conectar dois módulos, leia **os dois lados** (produtor e consumidor) e compare o shape campo a
campo contra o contrato acima. Ex.: `/search` (produtor) vs o que o `ContextBuilder` (consumidor)
espera. Divergência → corrige no módulo dono, atualiza `_workspace/CONTRACTS.md`.
