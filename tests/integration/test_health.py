"""Integration test for the health endpoint.

Uses FastAPI's TestClient (httpx transport) — no external network is touched.
"""

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
