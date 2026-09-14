"""Tests for the /papers endpoints."""


async def test_list_papers_returns_paginated_shape(client):
    response = await client.get("/api/v1/papers/")

    assert response.status_code == 200
    body = response.json()

    assert isinstance(body["papers"], list)
    assert isinstance(body["total"], int)
    assert body["total"] >= len(body["papers"])


async def test_list_papers_respects_limit(client):
    response = await client.get("/api/v1/papers/", params={"limit": 1, "offset": 0})

    assert response.status_code == 200
    assert len(response.json()["papers"]) <= 1


async def test_list_papers_rejects_invalid_limit(client):
    response = await client.get("/api/v1/papers/", params={"limit": 0})

    assert response.status_code == 422


async def test_get_paper_details_not_found(client):
    response = await client.get("/api/v1/papers/9999.99999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Paper not found"


async def test_get_paper_details_rejects_malformed_id(client):
    response = await client.get("/api/v1/papers/not-an-arxiv-id")

    assert response.status_code == 422
