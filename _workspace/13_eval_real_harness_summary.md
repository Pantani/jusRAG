# Tarefa 13.B.2 — eval-real harness (opt-in real providers)

## Objetivo

Permitir rodar a suíte completa de evals (§35-37) contra providers reais
(OpenAI / sentence-transformers / Ollama + Qdrant) sem quebrar o baseline
`make eval` (fake, determinístico, offline, CI).

## Como acionar

```bash
# CI baseline (fake providers, sem rede) — inalterado:
make eval

# Opt-in real (não usado por CI):
EVAL_PROVIDER=openai OPENAI_API_KEY=sk-... make eval-real
EVAL_PROVIDER=local make eval-real      # sentence-transformers + ollama
EVAL_PROVIDER=fake make eval-real       # equivalente a `make eval`

# Equivalente direto:
python -m packages.evals.run_all --provider=openai
python -m packages.evals.run_all --provider=local --llm-provider=fake
```

Pareamento default de LLM por embedding: `openai → openai`, `local → ollama`,
`fake → fake`. Pode ser sobrescrito com `--llm-provider`.

## Mudanças

| Arquivo | Mudança |
|--------|---------|
| `packages/evals/run_all.py` | argparse `--provider`/`--llm-provider`; `ProviderSelection`; pré-flight Qdrant; checagem OPENAI_API_KEY / Ollama; campo `provider` no JSON |
| `packages/evals/harness.py` | novo `build_real_harness()` reusando `_assemble()` com providers reais via selectors |
| `packages/evals/report.py` | seção `## Providers` no MD |
| `Makefile` | target `eval-real` (escape `$${EVAL_PROVIDER:-fake}`) |
| `tests/evals/test_run_all.py` | 7 testes novos cobrindo provider field, pré-flight, defaults |
| `.github/workflows/ci.yml` | **inalterado** — só `make eval` (fake) roda em CI |

## Pré-flight de dim mismatch

Em `_preflight_qdrant()`, ao escolher provider real, fazemos `GET
/collections/legal_chunks` direto no Qdrant via httpx e comparamos
`config.params.vectors.size` com `embedding_vector_size(settings)` (256 fake / 768
local / 1536 openai). Mismatch → `SystemExit` com mensagem operacional:

```
Qdrant collection 'legal_chunks' has vector size 256, but provider 'openai'
requires 1536. Recreate the collection:
  curl -X DELETE http://localhost:6333/collections/legal_chunks && make index-cdc
```

Nenhum DELETE automático — operação destrutiva exige ação explícita do operador.
Se a collection não existir (404), seguimos: o `index_chunks` inicial cria com
o tamanho correto.

## Mensagens de erro esperadas

| Cenário | Mensagem |
|--------|----------|
| `--provider=openai` sem `OPENAI_API_KEY` | `OPENAI_API_KEY is not set; cannot run eval with provider 'openai'. Export it (e.g. \`export OPENAI_API_KEY=sk-...\`) or pick another provider.` |
| `--provider=local` (LLM ollama default) com Ollama down | `Ollama is not reachable at http://ollama:11434 (...). Start it (e.g. \`make up\` with the local overlay) or pick another LLM provider.` |
| Qdrant offline | `Qdrant pre-flight failed: cannot reach http://localhost:6333 (...). Start it with \`make up\` before running eval-real.` |
| Collection com dim incompatível | (ver bloco acima) |

Todos abortam com exit code != 0 antes de qualquer chamada paga / lenta.

## Comportamento default preservado

- `python -m packages.evals.run_all` (sem flag) → ProviderSelection("fake","fake"),
  ignora env `EMBEDDING_PROVIDER`/`LLM_PROVIDER` (forçamos fake no env via
  `_apply_provider_env`).
- Teste `test_default_invocation_stays_on_fake_providers` cobre exatamente esse
  contrato: mesmo com `EMBEDDING_PROVIDER=openai` no ambiente, a invocação sem
  flag continua usando providers fake.

## Relatório

`data/generated/eval_report.json` ganha campo top-level:

```json
{
  "provider": {"embedding": "fake", "llm": "fake"},
  "golden": {...},
  "gate": {...},
  "metrics": {...}
}
```

E o `.md` ganha seção `## Providers` no topo.

## Testes

```
$ make eval
Provider: embedding=fake, llm=fake
Golden questions: 158 (in-scope 121, out-of-scope 37)
  [PASS] retrieval_recall_at_5 = 0.9669 (threshold 0.8)
  [PASS] citation_coverage = 1.0000 (threshold 0.9)
  [PASS] unsupported_legal_claim_rate = 0.0000 (threshold 0.05)
  [PASS] refusal_when_no_source_rate = 1.0000 (threshold 0.9)
Gate (strict): PASSED
```

```
$ pytest tests/evals/test_run_all.py -v
14 passed
```

Novos testes:
- `test_report_contains_provider_field_default_fake`
- `test_report_provider_field_reflects_selection`
- `test_markdown_report_renders_provider_header`
- `test_main_openai_without_api_key_exits_non_zero` (mock env, sem rede)
- `test_main_ollama_unreachable_exits_non_zero` (mock reach-check, sem rede)
- `test_default_invocation_stays_on_fake_providers`
- `test_resolve_providers_pairs_default_llm`

Full suite: `pytest` → **194 passed** (worktree global).

Lint/types nas mudanças próprias: `ruff check packages/evals tests/evals` →
clean; `mypy packages apps` → clean. (Erros de lint em
`_workspace/probes/probe_eval.py` são pré-existentes de outra sessão e fora do
escopo desta tarefa.)

## Decisão de design

**Flag única `--provider` controla embedding; `--llm-provider` separa LLM.**
Justificativa: dim-mismatch é problema exclusivo do embedding (collection
Qdrant); LLM é trocável a qualquer momento sem reindex. Permitir os dois separados
deixa o operador rodar, e.g., `local` embedding (rápido, gratuito) com `fake` LLM
para isolar regressão de retrieval sem custo de geração. Default pareado
(openai→openai, local→ollama) cobre o caminho comum.

## Não rodado (depende de chave)

`make eval-real` real com OpenAI/Ollama não foi executado — caminho de código
existe, é testável offline via mocks, e documentado.
