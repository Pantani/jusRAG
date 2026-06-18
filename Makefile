.PHONY: up down test lint format ingest-cdc ingest-case-law index-cdc search-demo ask-demo eval pull-models bootstrap-local up-local down-local restart-local wait-ollama pull-chat-model seed-local logs-local ui

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
	$(COMPOSE_LOCAL) exec -T api python -m apps.worker.jobs.ingest_cdc

ingest-case-law:
	$(COMPOSE_LOCAL) exec -T api python -m apps.worker.jobs.ingest_case_law

index-cdc:
	$(COMPOSE_LOCAL) exec -T api python -m apps.worker.jobs.index_cdc

search-demo:
	$(COMPOSE_LOCAL) exec -T api python -m apps.worker.jobs.search_demo

ask-demo:
	$(COMPOSE_LOCAL) exec -T api python -m apps.worker.jobs.ask_demo

eval:
	$(COMPOSE_LOCAL) exec -T api python -m packages.evals.run_all

# Streamlit demo UI. Roda no host e aponta para a API no Docker.
# Requer `pip install -e .` (ou pelo menos streamlit + requests) no .venv.
ui:
	JUSRAG_API_URL=$${JUSRAG_API_URL:-http://localhost:8000} streamlit run apps/web/app.py

# Pull local models into the **host** Ollama daemon (Phase 12). Ollama runs on
# the macOS host (Metal/GPU) and the API reaches it via host.docker.internal —
# see docker-compose.override.local.yml. `nomic-embed-text` is optional: the
# default embedding path uses sentence-transformers in-process.
pull-models:
	ollama pull llama3.1:8b
	ollama pull nomic-embed-text

# --- Local offline stack (Ollama + sentence-transformers) -------------------

COMPOSE_LOCAL = docker compose -f docker-compose.yml -f docker-compose.override.local.yml

up-local:
	$(COMPOSE_LOCAL) up -d --build

down-local:
	$(COMPOSE_LOCAL) down -v

logs-local:
	$(COMPOSE_LOCAL) logs -f api

# Derruba (com volumes) e sobe a stack offline limpa, sem baixar modelos nem
# ingerir. Útil quando a sessão atual travou ou para começar do zero.
restart-local:
	$(COMPOSE_LOCAL) down -v
	$(COMPOSE_LOCAL) up -d --build

# Espera o servidor Ollama (no host macOS) ficar respondendo (timeout 120s).
wait-ollama:
	@echo "Aguardando Ollama responder em http://localhost:11434..."
	@i=0; until curl -fsS http://localhost:11434/api/tags > /dev/null 2>&1; do \
		i=$$((i+1)); \
		if [ $$i -gt 60 ]; then echo "Ollama não respondeu em 120s. Rode: ollama serve"; exit 1; fi; \
		sleep 2; \
	done
	@echo "Ollama pronto."

# Baixa só o modelo de chat no host (llama3.1:8b ~ 4.7 GB na primeira vez).
pull-chat-model:
	ollama pull llama3.1:8b

# Popula CDC e indexa no Qdrant (assume stack já de pé).
seed-local:
	$(COMPOSE_LOCAL) exec -T api python -m apps.worker.jobs.ingest_cdc
	$(COMPOSE_LOCAL) exec -T api python -m apps.worker.jobs.index_cdc

# One-shot: derruba tudo, sobe a stack offline do zero, espera o Ollama
# ficar saudável, baixa o modelo de chat, popula CDC e indexa no Qdrant.
bootstrap-local: restart-local wait-ollama pull-chat-model seed-local
	@echo ""
	@echo "Pronto. Teste:"
	@echo "  curl http://localhost:8000/health"
	@echo "  curl -X POST http://localhost:8000/ask -H 'Content-Type: application/json' \\"
	@echo "    -d '{\"question\":\"Qual o prazo para reclamar de vício aparente em produto durável?\"}'"
