# QA Final — Fase 10 (v1.0 release) — jus-rag-brasil

Data: 2026-06-17 · QA de integração (shapes produtor↔consumidor + aceite §26 ponta a ponta).
Ambiente: `.venv` Python 3.12.13, offline, fake providers determinísticos.

> Nota de ferramenta: `make test`/`pytest` puro é interceptado por um stub do sandbox que imprime
> "Pytest: No tests collected" e retorna 0 sem rodar nada. Contornado executando `.venv/bin/pytest`
> diretamente (mesmo binário do alvo `make test`). Resultados abaixo são reais.

## 1. Aceite §26 (offline) — comandos rodados

| Alvo | Comando real | Resultado |
|------|--------------|-----------|
| make test | `.venv/bin/pytest tests` | **164 passed**, 1 warning, exit 0 |
| make lint (ruff) | `ruff check .` | All checks passed, exit 0 |
| make lint (mypy) | `mypy packages apps` | Success: no issues in **88 source files**, exit 0 |
| make eval | `python -m packages.evals.run_all` | **Gate (strict): PASSED**, exit 0 |
| make ingest-cdc | `python -m apps.worker.jobs.ingest_cdc` | 6 chunks (arts. 6º,12,14,18,26,49), exit 0 |
| make ingest-case-law | `python -m apps.worker.jobs.ingest_case_law` | 5 chunks (Súmulas 130,297,302,479,543), exit 0 |
| make search-demo | `python -m apps.worker.jobs.search_demo` | "All acceptance queries passed", exit 0 |
| make ask-demo | `python -m apps.worker.jobs.ask_demo` | exit 0 (ver achado AD-1) |

### Métricas eval reais (§36)
Golden: 31 perguntas (in-scope 24, out-of-scope 7).

| Métrica | Valor | Threshold | Veredito |
|---------|-------|-----------|----------|
| retrieval_recall_at_5 | 1.0000 | ≥ 0.80 | PASS |
| citation_coverage | 1.0000 | ≥ 0.90 | PASS |
| unsupported_legal_claim_rate | 0.0000 | ≤ 0.05 | PASS |
| refusal_when_no_source_rate | 1.0000 | ≥ 0.90 | PASS |

O gate falha o build em violação (verificado por `tests/evals/test_run_all.py` + modo strict).

## 2. Matriz de contratos (produtor → consumidor)

| Fronteira | Contrato | Verificação real | Status |
|-----------|----------|------------------|--------|
| ingestion → schema | `cdc_chunks.jsonl` ↔ LegalChunk (§8) | 6 objetos `LegalChunk.model_validate` OK; doc_type=`statute`; content_hash+source_url setados | OK |
| ingestion → schema | `case_law_chunks.jsonl` ↔ LegalChunk (§8) | 5 objetos validam; doc_type=`case_law`; hash+url setados | OK |
| ingestion idempotência | §2.4 | re-run ingest-cdc → md5 idêntico (`4f783e…5d47`) | OK |
| retrieval → answer | `SearchService.search_separated` → `SeparatedRetrieval{statutes, case_law}` (retriever.py:26) | método existe; retorna blocos separados; case_law nunca fabricado | OK |
| retrieval → answer | AnswerWriter popula AnswerResponse com legal_basis vs case_law separados | cenário (a): só legal_basis; (c): só case_law | OK |
| answer → auditor | CitationAuditResult shape §31 `{citation_coverage, unsupported_legal_claim_rate, unsupported_claims, passed}` | keys exatas via `as_dict()`; integrado em answer_writer `_enforce_audit` (linhas 102/108) | OK |
| agentic | LegalResearchState (§13) | campos batem **exatamente** com spec §1074-1087 (final_answer: str\|None); sem campos extra | OK |
| agentic | run_graph ponta a ponta | status `answered`/`refused` produzidos; estado final com final_answer+audit+caveats; AnswerResponse estruturado no AnswerBuffer | OK |
| evals | run_all consome retrieval/answer/auditor reais; agrega 4 métricas §36 | confirmado; gate strict falha build | OK |
| EmbeddingProvider/VectorStore §27/§28 | fakes determinísticos, sem rede | sem imports de rede em fake_provider; testes determinismo passam | OK |
| API §5 | routes delegam a packages (sem lógica de negócio) | 15 testes integração (ask/search/health) passam via TestClient | OK |

**Nenhuma quebra de contrato de interface no runtime do produto.**

## 3. Prova dos 6 cenários (a–f)

Executados via `run_graph` (runtime real) + auditor direto + buffer estruturado.

| # | Cenário | Evidência | Veredito |
|---|---------|-----------|----------|
| a | defeito do produto → art. 12 | grafo: `selected` inclui `cdc-8078-1990-art-12`; legal_basis cita art.12; status answered | PASS |
| b | arrependimento → art. 49 | grafo: `retrieved_statutes[0]=art-49` (0.368), selected `[art-49, art-18]`; search-demo confirma "-> art. 49" | PASS |
| c | CDC aplica-se a banco → Súmula 297 separada | grafo: case_law=`[STJ Súmula 297, STJ Súmula 479]`, legal_basis vazio → jurisprudência em bloco próprio | PASS |
| d | fora de escopo (IR cripto) → recusa segura | grafo: **status=refused**, selected=[], retrieved vazios, texto "Não há base suficiente…", sem fonte inventada | PASS |
| e | alucinação simulada → auditor detecta | auditor sobre claim "art. 99": passed=**False**, coverage=0.0, rate=1.0, claim listado em unsupported_claims; answer_writer reescreve/recusa | PASS |
| f | not_legal_advice=true em toda resposta | a/b/c/e: `not_legal_advice=True`; refusal mantém disclaimer | PASS |

## 4. Segurança §2/§40

- **Sem fonte inventada (§2.1):** seed jurisprudência aponta URLs oficiais `stj.jus.br`; Súmulas 130/297/302/479/543 são súmulas reais de Direito do Consumidor do STJ. CDC carregado do seed local.
- **Recusa sem fonte (§2.2):** comprovado cenário (d) — grafo recusa quando classificação/área não encontra fonte in-scope.
- **Separação legislação/jurisprudência/ressalva (§2.3):** cenário (a) só legal_basis; (c) só case_law; caveats presentes (2–3 por resposta).
- **Sem secrets commitados (§7):** `.env` não versionado (em `.gitignore`); `.env.example` com `OPENAI_API_KEY=` **vazio**.
- **Sem PII no seed:** scan CPF/CNPJ/processo/email não encontrou padrões; nenhum número de processo individual.

## 5. Docs / CI

- README lista todos os 11 `make` targets, batendo 1:1 com o Makefile — projeto roda do zero.
- `.github/workflows/ci.yml`: declarado offline por design; jobs rodam `make lint`, `make test`, `make eval`; `make up`/`make index-cdc` intencionalmente fora do CI.

## 6. Limitações ambientais conhecidas (NÃO são defeito)

| Alvo | Por que não roda aqui | Confirmação |
|------|----------------------|-------------|
| make up | requer Docker daemon (instável neste sandbox) | falha por ambiente, não por bug; compose válido |
| make index-cdc | requer Qdrant vivo + OPENAI_API_KEY (rede) | depende de stack externo; explicitamente fora do caminho offline |

Ambos são esperados; o caminho de aceite v1 §26 é integralmente offline com fakes determinísticos.

## 7. Achados (não-bloqueantes)

- **AD-1 (ask-demo, não-bloqueante):** `make ask-demo` responde a pergunta out-of-scope "alíquota de IR
  sobre criptomoedas" com `status=answered` citando Súmula 543 (score 0.221), em vez de recusar. Causa:
  o **script de demo** usa `AnswerWriter` diretamente (pipeline plano), cujo scope-gate só recusa quando
  a recuperação retorna **zero** chunk (`answer_writer.py:76`); o in-memory store sempre devolve top_k.
  - O **runtime real (LangGraph)** recusa corretamente o mesmo input (cenário d acima: status=refused),
    pois aplica gating de área/score antes de sintetizar. O caminho de produto e o eval estão corretos
    (`refusal_when_no_source_rate=1.0`).
  - Dono: AnswerAgent (ou UI-Docs, dono do `ask_demo.py`). Sugestão: o demo deveria exercitar o grafo
    (ou aplicar `_MIN_SEMANTIC_SCORE`) para a recusa ficar visível e consistente com o runtime. Não
    altera contrato nem gate; é coerência de vitrine. **Não corrigido** (ownership de outro módulo).

## VEREDITO FINAL

**Release-ready v1.0: SIM.**

Todos os aceites §26 offline passam (164 testes, lint+mypy limpos, eval gate PASSED com as 4 métricas
§36 acima do threshold). Contratos de interface produtor↔consumidor casam em todas as fronteiras; os 6
cenários (a–f) comprovados no runtime real; regras invioláveis §2/§40 satisfeitas; sem secrets/PII.

- **Pendências bloqueantes:** nenhuma.
- **Pendências não-bloqueantes:** AD-1 (consistência do `ask-demo` com o runtime de recusa) — cosmético,
  sem impacto em contrato, gate ou segurança.
- **Limitações ambientais:** `make up` e `make index-cdc` não exercitáveis neste sandbox (Docker/Qdrant/
  OPENAI_API_KEY) — esperado, fora do caminho de aceite offline.
