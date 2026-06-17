# Fase 11 (answer) — Seleção de LLMProvider por configuração (/ask offline)

## Escopo / ownership
Só seleção do LLM provider. NÃO toquei em `get_embedding_provider`/`get_vector_store`
(retrieval), `settings.py`, `packages/answer/*`, `index_cdc`, `rag`, README, Makefile.

## Mudanças
1. **`packages/llm/selector.py`** (novo) — `make_llm_provider(settings?) -> LLMProvider`,
   espelhando `packages/embeddings/selector.py`:
   - `settings.llm_provider == "fake"` → `FakeLLMProvider()` (determinístico, sem rede/chave).
   - `"openai"` → `OpenAILLMProvider(settings)` (erro explícito sem chave; sem fallback silencioso).
2. **`apps/api/dependencies.py`** — `get_llm_provider` agora delega a `make_llm_provider(settings)`
   (antes instanciava `OpenAILLMProvider` direto). Import trocado de `openai_provider` para
   `selector`. `get_answer_writer` inalterado: monta `AnswerWriter(service, llm)` com o LLM
   selecionado + o `SearchService` (retrieval já existente) ⇒ POST /ask funciona end-to-end offline
   quando `LLM_PROVIDER=fake` e `EMBEDDING_PROVIDER=fake`.

## test / lint (sem regressão)
- `make lint` → ruff: All checks passed; mypy: Success, no issues in 90 source files.
- `make test` → **166 passed**, 1 warning (StarletteDeprecationWarning, preexistente).

## Prova /ask end-to-end offline (stack real no ar)
Setup: api/postgres/qdrant/redis Up; Qdrant `legal_chunks` com 11 pontos em dim=256 (fake);
`OPENAI_API_KEY` unset. TestClient local com `LLM_PROVIDER=fake EMBEDDING_PROVIDER=fake
QDRANT_URL=http://localhost:6333` (Qdrant real, não InMemory).

**(a) "O fornecedor responde por defeito do produto?"** → `http=200 status=answered`,
sources `[art-26, art-14, art-12, art-18]` (cita **art. 12** entre outros), `not_legal_advice=true`.

**(b) recusa out-of-scope (tributário/cripto)** → `status=refused`, `sources=[]`, `not_legal_advice=true`:
- "Como declarar criptomoedas e bitcoin na malha fina da Receita Federal?" → refused.
- "Qual a alíquota do imposto territorial rural cobrado pela Receita Federal?" → refused.

**(c)** `not_legal_advice=true` em todas as respostas acima.

## Ressalva (fora do meu ownership — NÃO é regressão)
O fraseado literal "Qual a alíquota do imposto de renda sobre criptomoedas?" retorna `answered`
citando `stj-sumula-543` (não `refused`). Causa: falso positivo léxico do `FakeEmbeddingProvider`
— Súmula 543 marca `semantic_score=0.343` (> `min_semantic_score=0.20`) por tokens compartilhados,
enquanto os statutes ficam abaixo do limiar. Comportamento **idêntico no harness offline puro
(InMemoryVectorStore)**, logo independe da seleção de provider: é a heurística `min_semantic_score`
do `AnswerWriter` (ownership answer-writer/retrieval), cujo gate robusto está previsto para o Area
Classifier (Fase 7) + CitationAuditor, conforme CONTRACTS.md. O golden dataset usa fraseados
out-of-scope que não disparam essa colisão → `refusal_when_no_source_rate=1.0`. A recusa offline
está provada em (b) com perguntas tributárias do próprio dataset.

## openai sem chave → erro explícito preservado
`LLM_PROVIDER=openai` + `OPENAI_API_KEY` unset → `RuntimeError: OPENAI_API_KEY is not set ...`
(levantado em `get_llm_provider` → `make_llm_provider` → `OpenAILLMProvider.__init__`). Sem
fallback silencioso.

## CONTRACTS.md
Sem mudança de shape (DI interna). A seção "Settings" já previa que `dependencies.py` escolheria
`FakeLLMProvider`/`OpenAILLMProvider` conforme `LLM_PROVIDER`; agora implementado via selector.
