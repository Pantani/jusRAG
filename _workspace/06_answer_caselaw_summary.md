# Fase 6 (v0.6) — Answer: bloco de jurisprudência na resposta (lado AnswerAgent)

Fonte: §2.3 (separar legislação/jurisprudência), §12.7, §22 (aceite), §31–34, §41.
Consome `SearchService.search_separated(...) -> SeparatedRetrieval{statutes[], case_law[]}`
(entregue pelo RetrievalAgent na Fase 6). Authority STJ súmula = 0.88 (já no retrieval).

## Mudanças (ownership answer)

- **`packages/answer/schemas.py`** — novo `CaseLawItem`
  `{chunk_id, court?, case_number?, title, ementa, source_url?}`. `AnswerResponse.case_law`
  passou de `list[dict]` para `list[CaseLawItem]` (tipado, serializável no `/ask`). Populado
  SOMENTE com jurisprudência efetivamente recuperada — nunca inventado (§22).
- **`packages/answer/formatter.py`** — `build_answer(draft, context, case_law_chunks=None)`:
  - `case_law` é montado por `_case_law_from_chunks()` a partir dos `RetrievedChunk` de
    jurisprudência (filtra `doc_type==case_law`); court/case_number vêm do `metadata`,
    ementa do `chunk.text`, `source_url`/title da `CitationRef`. Bloco vazio ⇒ não aparece.
  - `legal_basis` agora carrega **só legislação**: citações para chunks `case_law` são
    descartadas do `legal_basis` (separação §2.3). Jurisprudência só no bloco `case_law`.
- **`packages/answer/answer_writer.py`** — `write()` usa `search_separated`:
  - separa `grounded_statutes` / `grounded_case_law` (cada um filtrado por
    `min_semantic_score`).
  - Gate de escopo (§2.2): recusa só quando NEM statute NEM case_law em escopo. Pergunta
    cuja base é uma súmula recuperada deixa de ser recusada como out-of-scope.
  - Contexto auditado = `statutes + case_law` (legislação primeiro): o LLM e o auditor veem
    legislação **e** jurisprudência, então uma súmula alucinada fora do contexto é detectada
    pelo auditor (§2.1, §31). `build_answer(..., grounded_case_law)` popula o bloco.
- **`packages/answer/prompts.py`** — instrui o LLM a separar fundamento legal (artigos em
  `legal_basis`) de jurisprudência, e a **nunca** afirmar súmula/precedente/tese ausente do
  CONTEXTO; a jurisprudência relevante é montada das fontes recuperadas, não inventada.
- **`packages/answer/citation_auditor.py`** — auditoria de claims de jurisprudência:
  `_SUMULA_REF` extrai número de súmula (`Súmula 297`, `súmula nº 297`, e `sumula-297`
  no chunk_id). `_grounds` agora exige que todo número de súmula citado pelo claim apareça
  no chunk que o sustenta (`_chunk_sumulas` = texto ∪ chunk_id) — espelhando a regra de
  artigo. Súmula citada mas não recuperada ⇒ sempre `unsupported`. **Threshold (0.05)
  inalterado**; corrigida a extração/verificação, não relaxado o gate.
- **`apps/api/routes/ask.py`** — inalterado (já só delega ao `AnswerWriter`).
- **`apps/worker/jobs/ask_demo.py`** — indexa statutes + case_law; nova pergunta
  consumerista de jurisprudência; imprime o bloco `case_law` (court, número, ementa, url).

## Como o bloco de jurisprudência é montado e auditado

1. `search_separated` devolve `statutes[]` e `case_law[]` ranqueados/truncados isoladamente.
2. Filtro `min_semantic_score` em cada bloco → `grounded_statutes`, `grounded_case_law`.
3. Recusa segura se ambos vazios; caso contrário contexto = statutes+case_law.
4. LLM gera draft sobre esse contexto. `formatter`:
   - `legal_basis` ← só citações de statute (case_law removido daqui).
   - `case_law` ← `_case_law_from_chunks(grounded_case_law)` (fonte-vinculado, §22).
5. Auditoria (`audit_answer`) sobre `short_answer` + `legal_basis`; se o draft afirma uma
   súmula sem suporte no contexto, `_grounds` reprova → writer reescreve/recusa. O bloco
   `case_law` é seguro por construção (só fontes recuperadas), não precisa de poda.

## Prova (a–d)

- **(a)** `tests/integration/test_ask.py::test_ask_returns_separated_case_law_block` e
  `tests/unit/answer/test_answer_writer.py::test_consumer_question_returns_separated_case_law_block`:
  "CDC se aplica a banco?" → `case_law` contém `stj-sumula-297` (court=STJ, source_url
  presente), e nenhum `stj-sumula-*` aparece em `legal_basis` (blocos separados).
- **(b)** `test_ask_no_case_law_when_irrelevant` /
  `test_question_without_relevant_case_law_has_no_block`: pergunta statute-only →
  `case_law == []`, nada inventado.
- **(c)** `tests/unit/answer/test_citation_auditor.py::test_hallucinated_sumula_is_detected`
  (auditor puro) e `::test_writer_removes_hallucinated_sumula` (end-to-end): LLM fake cita
  "Súmula 999" fora do contexto → auditor flag → resposta final sem "999", `case_law==[]`,
  `audit.passed==True`. Também `test_supported_sumula_claim_is_covered` (súmula real passa).
- **(d)** `not_legal_advice=true` mantido em todos os testes acima e nos da Fase 4.

## Saída real

`make ask-demo` (pergunta de jurisprudência):
```
PERGUNTA: O CDC se aplica a banco e instituição financeira?
  status: answered
  short_answer: Com base em STJ Súmula 297, O Código de Defesa do Consumidor é aplicável às instituições financeiras.
  case_law: STJ Súmula 297 -> O Código de Defesa do Consumidor é aplicável às instituições financeiras.  source_url=https://www.stj.jus.br/.../capSumula297.pdf
  case_law: STJ Súmula 479 -> As instituições financeiras respondem objetivamente ...  source_url=.../capSumula479.pdf
  sources: ['stj-sumula-297', 'stj-sumula-479']
  audit: coverage=1.00 unsupported_rate=0.00 passed=True
  not_legal_advice: True
```

```
make test  -> 134 passed (era 125; +9 answer/jurisprudência)
make lint  -> ruff: All checks passed ; mypy: Success, 69 files
```

Não-regressão Fases 4/5 confirmada (mesma suíte): out-of-scope recusa
(`test_ask_out_of_scope_refuses`), citação fora do contexto removida
(`test_ask_never_cites_outside_context`), alucinação de artigo detectada/removida
(`test_writer_drops_hallucinated_claim_and_attaches_audit`) — todos passando.

## Aceite §22 (lado answer)

Resposta exibe fundamento legal (`legal_basis`, legislação) e jurisprudência (`case_law`)
SEPARADAMENTE; jurisprudência sem fonte recuperada não é exibida (bloco vazio) nem inventada;
súmula alucinada pelo LLM é barrada pelo auditor.
