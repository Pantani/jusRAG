.PHONY: up down test lint format ingest-cdc ingest-case-law index-cdc search-demo ask-demo eval eval-real pull-models

up:
	docker compose up --build

down:
	docker compose down -v

test:
	pytest

lint:
	ruff check .
	mypy packages apps

format:
	ruff format .

ingest-cdc:
	python -m apps.worker.jobs.ingest_cdc

ingest-case-law:
	python -m apps.worker.jobs.ingest_case_law

index-cdc:
	python -m apps.worker.jobs.index_cdc

search-demo:
	python -m apps.worker.jobs.search_demo

ask-demo:
	python -m apps.worker.jobs.ask_demo

eval:
	python -m packages.evals.run_all

# Opt-in eval against real providers — NOT used by CI. Requires a running Qdrant
# stack (`make up`) whose `legal_chunks` collection matches the chosen provider's
# vector size; run-time pre-flight aborts with a recreate command on mismatch.
# Usage:
#   EVAL_PROVIDER=openai OPENAI_API_KEY=sk-... make eval-real
#   EVAL_PROVIDER=local make eval-real            # sentence-transformers + ollama
#   EVAL_PROVIDER=fake make eval-real             # equivalent to `make eval`
#
# `EVAL_SAMPLE_LLM=N` (optional): run LLM-bound metrics over a stratified
# subset of N golden questions (N//2 in-scope + N//2 OOS); retrieval stays
# full. The §36 gate becomes informational. Useful to validate plumbing of
# slow local models (e.g. CPU Ollama: ~25min for N=10 vs ~40h full).
#   EVAL_PROVIDER=local EVAL_SAMPLE_LLM=10 make eval-real
eval-real:
	python -m packages.evals.run_all \
		--provider=$${EVAL_PROVIDER:-fake} \
		--sample-llm=$${EVAL_SAMPLE_LLM:-0}

# Pull local models into the Ollama container (Phase 12). Requires the
# `docker-compose.override.local.yml` overlay to be active. `nomic-embed-text`
# is optional: default embedding path uses sentence-transformers in-process.
pull-models:
	docker compose -f docker-compose.yml -f docker-compose.override.local.yml exec ollama ollama pull llama3.1:8b
	docker compose -f docker-compose.yml -f docker-compose.override.local.yml exec ollama ollama pull nomic-embed-text
