.PHONY: up down test lint format ingest-cdc ingest-case-law index-cdc search-demo ask-demo eval pull-models

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

# Pull local models into the Ollama container (Phase 12). Requires the
# `docker-compose.override.local.yml` overlay to be active. `nomic-embed-text`
# is optional: default embedding path uses sentence-transformers in-process.
pull-models:
	docker compose -f docker-compose.yml -f docker-compose.override.local.yml exec ollama ollama pull llama3.1:8b
	docker compose -f docker-compose.yml -f docker-compose.override.local.yml exec ollama ollama pull nomic-embed-text
