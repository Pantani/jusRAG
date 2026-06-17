# AD-1 fix — ask-demo out-of-scope refusal

## Problema
`apps/worker/jobs/ask_demo.py` chamava o `AnswerWriter` direto. O gate de escopo do
writer (`_MIN_SEMANTIC_SCORE`, answer_writer.py:75) só recusa quando a recuperação é
vazia. Para "Qual a alíquota do imposto de renda sobre criptomoedas?" o retrieval ainda
trazia uma súmula irrelevante (STJ 543) acima do threshold → `status=answered` citando
fonte fora de contexto. O runtime LangGraph já recusava o mesmo input.

## Causa raiz
O grafo (`packages/agents`) classifica a área (`LegalAreaClassifier`, `legal_area=tax`
para cripto) e os researchers filtram retrieval por `legal_area` → `selected_context`
vazio → `_route_after_select` → recusa segura. O caminho direto do `AnswerWriter` não
tem esse filtro por área, só o gate semântico, que aqui não dispara.

## Opção escolhida: A (rotear a demo pelo run_graph)
A vitrine agora roda o mesmo runtime agentic do produto. `DemoRuntime` constrói o grafo
com `build_graph(... buffer=AnswerBuffer())`, invoca por pergunta e expõe tanto o §13
`LegalResearchState` (status/final_answer/caveats) quanto o `AnswerResponse` estruturado
do buffer (legal_basis/case_law/sources) para impressão.

### Trade-off A vs B
- **A (escolhida):** reusa o gate de escopo real (classificação + filtro por área), zero
  duplicação de lógica de segurança, demo passa a refletir o produto. Custo: a demo
  depende de `packages/agents` e acessa o `AnswerBuffer` para a saída estruturada (o
  `audit` schema fica em `state.audit`, não no `AnswerResponse` do buffer, então a linha
  `audit:` não é impressa para respostas answered — não exigido pelo aceite).
- **B (descartada):** injetar o classifier no `AnswerWriter` endureceria o caminho
  direto, mas duplicaria o gate de escopo já existente no grafo e deixaria dois caminhos
  divergentes para manter. A reusa a fonte única de verdade. Sem relaxar nada em ambos.

Nada foi relaxado: `_MIN_SEMANTIC_SCORE` intacto; separação legislação/jurisprudência e
aviso §41 preservados (saída do risk_checker).

## Saída real de `make ask-demo` (4 casos)
1. defeito do produto → `status=answered`, legal_basis inclui **art. 12** (+ 14, 18, 26).
2. arrependimento compra online → `status=answered`, legal_basis lidera **art. 49**.
3. CDC aplica-se a banco → `status=answered`, case_law **STJ Súmula 297** (+ 479),
   separada da legislação.
4. imposto sobre cripto → `status=refused`, sources `[]`, sem citar súmula/artigo
   irrelevante, com a short_answer de recusa segura.

## Teste
`tests/integration/test_ask_demo.py` (novo, offline):
- `test_out_of_scope_crypto_question_is_refused` — status=refused, sem legal_basis/case_law.
- `test_in_scope_consumer_questions_stay_answered` — art.12, art.49, Súmula 297.

## Validação
- `make ask-demo`: 4 casos conforme acima (capturado).
- `make test`: 166 passed.
- `make lint`: ruff All checks passed; mypy Success (88 files).

## Arquivos tocados
- `apps/worker/jobs/ask_demo.py` (reescrito para `DemoRuntime` via run_graph).
- `tests/integration/test_ask_demo.py` (novo).
Não tocados: rag, ingestion, legal_types, Makefile, pyproject, README/docs, .github.
