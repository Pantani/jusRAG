.PHONY: up down test lint format ingest-cdc ingest-case-law index-cdc search-demo ask-demo eval

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
