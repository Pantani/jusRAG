# Tarefa 13.B.4 — UI/Docs update for Phase 13 (v1.2)

## Arquivos editados

- `README.md` — status v1.0 → v1.2; seção Escopo do MVP reescrita (CDC integral 130 chunks vendored Planalto + STJ 30 entradas com breakdown verified/needs_review); novo bloco "Retrieval híbrido (opt-in)"; tabela `make` ganha linha `eval-real` com uso; bloco "Qualidade e avaliação" passa a reportar métricas atuais sobre o golden de 158 perguntas.
- `docs/evaluation.md` — reescrito: nova seção `make eval` vs `make eval-real` (pré-flight Qdrant, providers opt-in); golden atualizado para 158 (121 in-scope + 37 OOS); métricas atuais (recall=0.967, coverage=1.0, unsupp=0.0, refusal=1.0); seção "Como interpretar regressões" mapeia sintoma→causa→owner e fixa quando recalibrar threshold vs corrigir produtor da métrica.
- `docs/limitations.md` — removida limitação "seed restrito a 6 artigos / 5 súmulas"; adicionada pendência de curadoria humana de 25/30 entradas STJ; adicionadas limitações de embeddings PT vs EN, modelos locais pequenos (1b/3b) e `llama3.1:8b` CPU; adicionada limitação de hybrid retrieval ainda opt-in sem ranking calibrado em produção; tabela de riscos ganha linha para `verification_status`.
- `docs/source-policy.md` — seção "CDC seed" promovida para "CDC integral (Lei 8.078/1990) — v1.2" descrevendo Planalto HTML vendored, SHA256 no frontmatter e loader determinístico HTML→md; nova seção "Jurisprudência STJ (v1.2)" documentando origem, recorte, inclusões/exclusões e política `needs_review`.

## Validação

- `make lint` → ruff `All checks passed!` + mypy `Success: no issues found in 93 source files`.
- `make test` → **194 passed**, 1 warning benigno (StarletteDeprecationWarning pré-existente).

Apenas docs/Markdown foram editados; nenhum código tocado.
