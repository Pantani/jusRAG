# Fase 5 — Auditor de citações (v0.5) — answer / CitationAuditAgent

Data: 2026-06-17. Agente: answer. Skills: legal-rag-safety, legal-rag-contracts.

## Arquivos

Criados:
- `packages/answer/citation_auditor.py` — CitationAuditor puro (§31).
- `packages/agents/{__init__,citation_auditor}.py` — nó de runtime (Fase 7, sem LangGraph ainda).
- `tests/unit/answer/test_citation_auditor.py` — 8 testes (puro + end-to-end alucinação).

Editados (ownership answer):
- `packages/answer/schemas.py` — `CitationAudit` + campo `AnswerResponse.audit`.
- `packages/answer/answer_writer.py` — auditoria pós-draft + reescrita/recusa.
- `apps/worker/jobs/ask_demo.py` — imprime linha `audit:` (visibilidade).

NÃO toquei: `packages/legal_types`, `packages/rag`, `packages/ingestion`, `Makefile`,
`pyproject.toml`. NÃO criei `packages/evals` nem `tests/evals/` (eval-agent).

## Shape do CitationAuditor (§31, EXATO)

`audit_claims(short_answer, legal_basis: list[LegalClaim], chunks: list[AuditChunk],
*, max_unsupported_rate=0.05) -> CitationAuditResult`, onde
`CitationAuditResult{citation_coverage: float, unsupported_legal_claim_rate: float,
unsupported_claims: list[str], passed: bool}` (+ `.as_dict()`).
Dataclasses frozen `AuditChunk{chunk_id,text}`, `LegalClaim{text, cited_ids:tuple}`.

Extração de claims: cada `legal_basis` é um claim; sentenças do `short_answer` que
referenciam artigo (`art. N`) ou usam marcador jurídico viram claims. O split de
sentenças protege abreviações (`art.`, `arts.`, `inc.`, `par.`, `al.`, `n.`) via
placeholder — caso contrário "art." quebra a sentença e gera um fragmento fantasma.

Suporte de um claim: existe chunk (restrito aos `cited_ids` quando há citação) com
sobreposição léxica Jaccard ≥ 0.18 (tokens sem acento, sem stopwords) **e** que contém
todo `art. N` citado pelo claim. Artigo alucinado (não recuperado) → sempre
`unsupported`, mesmo com wording parecido. Sem claim jurídico → cobertura 1.0.
`passed = unsupported_legal_claim_rate <= 0.05` (§36).

## Reescrita / recusa (§21, §2.2, §40)

`AnswerWriter.write`: retrieve → context → LLM → format → **auditoria**. Se reprova:
1. Reescreve conservador: remove os `legal_basis` cujo `text` está em
   `unsupported_claims`; se o `short_answer` foi flagado, adota o primeiro basis suportado.
2. Re-audita o resultado (métricas descrevem a resposta REALMENTE retornada).
3. Se sobrar < 1 basis suportado, ou o re-audit ainda falhar → **recusa segura**
   (`status=refused`, `legal_basis=[]`, `audit` anexado).
A recusa não depende mais só do `_MIN_SEMANTIC_SCORE` (1ª passada heurística); o gate
robusto é o auditor de claims.

## Prova da alucinação simulada

`_HallucinatingLLM` (fake) força um `legal_basis` citando `art. 999 do CDC` (nunca
recuperado) junto de um claim genuíno sobre `art. 12`. Resultado end-to-end:
```text
status answered
basis ['Segundo o art. 12, o fabricante e o impo...']   # art. 999 REMOVIDO
audit {citation_coverage: 1.0, unsupported_legal_claim_rate: 0.0, passed: True}
```
O auditor detecta o art. 999 antes da reescrita
(`test_audit_answer_flags_hallucination_before_rewrite`: `passed=False`,
`unsupported_claims` contém o claim do 999); a resposta final o remove e mantém o art. 12.
Testes puros cobrem: claim suportado (cov 1.0), artigo alucinado detectado (cov 0.0,
passed False), métricas como fração (0.5/0.5), citação ao chunk errado não resgatável,
sem claim jurídico = vacuamente coberto.

## Bug encontrado e corrigido (não relaxado)

Conforme o protocolo (claim sem fonte passando = bug do auditor, não relaxar threshold):
o split de sentenças quebrava em `art.`, criando o fragmento `"Com base em ... art."`
classificado como claim jurídico sem suporte → recusa indevida de resposta legítima do
FakeLLM (visível só sob ordem de testes que aqueciam o cliente). Corrigido na extração
(proteção de abreviações), sem mexer no limiar.

## Saída de test/lint (capturada)

- `pytest tests/` (cache limpo): **105 passed**, 1 warning (StarletteDeprecation benigno).
- `make lint`: `ruff check .` All checks passed; `mypy` Success: no issues in 64 files.
- `ruff --select C901` nos 3 arquivos core: No issues found (CC ≤ 10).
- `make ask-demo` (dados reais, offline): in-scope `answered` com
  `audit: coverage=1.00 unsupported_rate=0.00 passed=True`; out-of-scope `refused`, sources [].

## Contrato para o eval-agent

Reusar `audit_claims` / `audit_answer` e as métricas `citation_coverage` e
`unsupported_legal_claim_rate` do `CitationAuditResult`. Threshold v1 (§36):
`unsupported_legal_claim_rate ≤ 0.05`. Detalhes I/O em `_workspace/CONTRACTS.md`
("Camada de auditoria — Fase 5"). NÃO relaxar o limiar para passar evals de alucinação.
