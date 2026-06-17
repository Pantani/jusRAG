"""FastAPI application entrypoint.

Assembles the app and mounts routers. No business logic lives here; each router
delegates to `packages/`. This file is a coordination point (§54) — other agents
request route additions via the orchestrator.
"""

from fastapi import FastAPI

from apps.api.routes import ask, health, search


def create_app() -> FastAPI:
    app = FastAPI(
        title="JusRAG Brasil",
        version="0.1.0",
        description=(
            "Open-source Brazilian legal-research copilot (RAG with verifiable "
            "citations). Not a legal-advice product."
        ),
    )
    app.include_router(health.router)
    app.include_router(search.router)
    app.include_router(ask.router)
    return app


app = create_app()
