# Fix: gate de escopo do AnswerWriter não pré-recusa UNKNOWN (CodeRabbit #3)

## Escopo
Ownership tocado: `packages/answer/answer_writer.py`, `tests/unit/answer/test_answer_writer.py`.
Nada em `packages/agents/`, `packages/evals/`, rotas ou jobs. Eval revalidado pelo orquestrador
(eval-agent) depois deste fix — não editei evals.

## Bug
`_is_out_of_scope(q) = not is_in_scope(classify_area(q))`, rodando ANTES do retrieval.
`classify_area` devolve `UNKNOWN` em dois casos colapsados no mesmo enum:
- (a) regime corpus-less com termo discriminante (previdência, INSS, falência, INPI, ambiental…) — de fato fora de escopo;
- (b) SEM evidência de keyword — pergunta possivelmente in-corpus que o mapa de keywords não reconheceu.

Como o gate tratava qualquer `UNKNOWN` como fora de escopo, perguntas reais com base no corpus mas sem
keyword forte (ex.: "arrolamento dos bens deixados" → inventário, CC art. 610 / CPC) eram RECUSADAS
antes do retrieval, contrariando o contrato dos researcher nodes (§14/§15.2): `UNKNOWN` pula o filtro
`legal_area` justamente para uma fonte real ainda surgir.

## Diff (núcleo)
`packages/answer/answer_writer.py`, `_is_out_of_scope`:

```python
def _is_out_of_scope(question: str) -> bool:
    area = classify_area(question)
    if area is LegalArea.UNKNOWN:
        return False  # sem evidência / corpus-less: retrieval+auditor decidem grounding
    return not is_in_scope(area)
```

- `administrative` (classe DEFINIDA, fora de `IN_SCOPE_AREAS`) continua pré-recusando.
- `UNKNOWN` prossegue ao retrieval.
- Import adicionado: `from packages.legal_types.enums import LegalArea` (ruff isort ok).
- Comentários do gate e do `write()` atualizados para o novo invariante.

## Racional §2.2 (não afrouxa a recusa)
A recusa segura de `UNKNOWN` apenas MUDA de autoridade: sai de um gate de keyword cego e passa para o
grounding/auditor — o guard correto. Dois pontos downstream já existentes garantem o §2.2:
1. `if not grounded_statutes and not grounded_case_law: build_refusal(...)` — retrieval sem base
   suficiente (≥ `_MIN_SEMANTIC_SCORE`) recusa. Regimes corpus-less que classificam `UNKNOWN`
   (previdência/INSS/falência/…) caem aqui: o corpus não tem suas fontes → retrieval vazio → recusa.
2. CitationAuditor (§31) barra claims sem suporte; `_audit_and_enforce` reescreve conservador ou recusa.

Alinhado com a "Limitação conhecida" já documentada e com `run_classify_area` (que anexa caveat de OOS
mas não zera retrieval).

## Trade-off honesto
O guard de `UNKNOWN` passa a depender de grounding+auditor, não da pré-recusa. Implicações:
- Um regime corpus-less NÃO coberto por `_OUT_OF_SCOPE_TERMS` e que classifique `UNKNOWN` agora só é
  barrado se o retrieval não trouxer base ≥ threshold. Com o fake embedding (lexical) e o corpus
  multi-área, uma pergunta OOS pode casar fracamente em algum artigo; a defesa real é o
  `_MIN_SEMANTIC_SCORE` + auditor. Não observei vazamento nos testes do módulo, mas a métrica
  `refusal_when_no_source_rate` (§36) muda de comportamento e é revalidada pelo eval-agent.
- `administrative` segue com classe própria e continua pré-recusando — sem regressão nesse caminho.

## Testes (antes/depois)
Antes: `tests/unit/answer/test_answer_writer.py` cobria refusal OOS via
`test_out_of_scope_question_refuses_safely` ("imposto de renda sobre criptomoedas" → classifica `tax`,
in-scope; recusa por retrieval sem base no corpus CDC fake — não depende do gate de `UNKNOWN`).

Adicionados:
- `test_administrative_question_classifies_to_defined_out_of_scope_area` — precondição: improbidade
  administrativa → `LegalArea.ADMINISTRATIVE`; `_is_out_of_scope` True.
- `test_administrative_question_refuses_safely` — (a) classe definida OOS ainda pré-recusa (REFUSED,
  `legal_basis == []`).
- `test_unknown_no_evidence_question_is_not_pre_refused_by_scope_gate` — (b) "arrolamento dos bens
  deixados" → `UNKNOWN`; `_is_out_of_scope(...) is False`.
- `test_unknown_question_can_be_answered_when_retrieval_grounds_it` — (b) e2e: pergunta classificada
  `UNKNOWN` ("O fabricante e o importador respondem pela reparacao dos danos?") chega ao retrieval,
  casa art. 12 (score ~0.67 ≥ 0.29) e é ANSWERED com `sources`. Prova que `UNKNOWN` não é pré-recusado.

Recusa de `administrative` preservada; nenhum teste existente quebrado.

## Lint/test reais (rodados)
- `pytest tests/unit/answer/` → 30 passed.
- `ruff check packages/answer packages/llm tests/unit/answer` → All checks passed (após `--fix` no
  isort do novo import).
- `mypy packages/answer packages/llm` (strict) → Success: no issues found in 12 source files.
- C90: `_is_out_of_scope` permanece trivial (CC bem abaixo de 10).
- Offline: usa apenas FakeEmbeddingProvider/FakeLLMProvider; sem rede.

## Para o orquestrador
Rodar eval-agent para revalidar §36, em especial `refusal_when_no_source_rate` (≥ 0.90 OOS) e
`unsupported_legal_claim_rate` (≤ 0.05), já que a decisão de `UNKNOWN` migrou para grounding/auditor.
