"""Tests for the /ping and /health endpoints."""


async def test_ping_returns_pong(client):
    response = await client.get("/api/v1/ping")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "pong"}


async def test_health_reports_service_statuses(client):
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()

    assert body["status"] in {"ok", "degraded"}
    assert "database" in body["services"]
    assert "ollama" in body["services"]
    assert body["services"]["database"]["status"] in {"healthy", "unhealthy"}
