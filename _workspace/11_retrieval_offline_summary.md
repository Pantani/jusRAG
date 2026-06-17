# Fase 11 — EmbeddingProvider selecionável por config (modo offline)

Dono: retrieval. Habilita `EMBEDDING_PROVIDER=fake` no caminho de recuperação
(API DI + index-cdc) sem exigir `OPENAI_API_KEY`, persistindo vetores fake
determinísticos no Qdrant real.

## Mudanças (ownership respeitado)

- **`packages/embeddings/selector.py`** (novo): fonte única de seleção.
  - `make_embedding_provider(settings) -> EmbeddingProvider`: `fake` →
    `FakeEmbeddingProvider()`; `openai` → `OpenAIEmbeddingProvider(settings)`
    (mantém o raise explícito sem chave — **sem fallback silencioso**).
  - `embedding_vector_size(settings) -> int`: 1536 (OpenAI) ou `FakeEmbeddingProvider().dim`
    (256) para a fake. Garante que a collection `legal_chunks` case com o provider.
- **`apps/api/dependencies.py`**: `get_embedding_provider` e `get_vector_store`
  passam a usar o selector. `get_llm_provider`/`get_answer_writer` **intactos**.
- **`apps/worker/jobs/index_cdc.py`**: `main()` honra `settings.embedding_provider`
  via selector; dimensão da collection derivada do provider. Idempotência por
  `chunk_id` inalterada.
- **`packages/storage/qdrant.py`** (bug pré-existente, mesmo ownership): `search`
  usava `QdrantClient.search`, removido no qdrant-client 1.18. Trocado por
  `query_points(...).points`. Sem isto, `/search` na stack real estourava
  `AttributeError`. Indexação (`upsert`) não foi afetada.

## Dimensão da collection

`legal_chunks` é criada com a dimensão do provider **em uso**: 256 (fake) ou 1536
(openai), distance Cosine. **Trocar de provider numa collection existente exige
recriá-la** (`make down`/recriar a collection) — dimensões incompatíveis.

## Prova na stack real (api/postgres/qdrant/redis no ar, OPENAI_API_KEY unset)

- `EMBEDDING_PROVIDER=fake make index-cdc` (run 1): `Indexed 11 chunk(s)`.
- run 2 (idempotência): `Indexed 11 chunk(s)`; collection segue com
  `points_count=11`, `dim=256`, `distance=Cosine`. Sem erro de chave.
- `/search` via TestClient (`EMBEDDING_PROVIDER=fake`, `QDRANT_URL=http://localhost:6333`),
  contra o Qdrant real:
  - `"defeito do produto"` → 200, top `cdc-8078-1990-art-12` (art. 12, score 0.421).
  - `"arrependimento"` → 200, top `cdc-8078-1990-art-49` (art. 49, score 0.394).
- `EMBEDDING_PROVIDER=openai` sem chave → `RuntimeError: OPENAI_API_KEY is not set`
  (raise explícito preservado).

## Nota para o orquestrador

Para `/search` responder **dentro do container** da API com a fake, o serviço da
API precisa do env `EMBEDDING_PROVIDER=fake` (e `QDRANT_URL` apontando para o
Qdrant da compose). A collection deve estar com dim=256 (recriar se foi indexada
com openai/1536). A prova acima foi feita via TestClient local apontando para o
Qdrant real da compose.

## test/lint

- `make lint`: ruff `All checks passed!`; mypy `Success: no issues found in 89 source files`.
- `make test`: `166 passed`. Sem regressão offline. CC ≤ 10 (selector trivial).
