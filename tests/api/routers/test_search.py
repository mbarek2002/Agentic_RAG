from src.main import app


async def test_search_endpoint_basic(client):
    response = await client.post("/api/v1/search/", json={"query": "neural networks", "size": 5})

    assert response.status_code == 200
    data = response.json()

    assert data["query"] == "neural networks"
    assert data["total"] == 0
    assert data["hits"] == []
    assert data["size"] == 5
    assert data["from"] == 0
    assert data["search_mode"] == "bm25"


async def test_search_endpoint_with_latest_papers(client):
    response = await client.post("/api/v1/search/", json={"query": "transformers", "latest_papers": True})

    assert response.status_code == 200
    assert response.json()["query"] == "transformers"


async def test_search_endpoint_with_categories(client):
    response = await client.post("/api/v1/search/", json={"query": "computer vision", "categories": ["cs.CV", "cs.AI"]})

    assert response.status_code == 200


async def test_search_endpoint_pagination(client):
    response = await client.post("/api/v1/search/", json={"query": "attention", "size": 5, "from": 10})

    assert response.status_code == 200
    data = response.json()
    assert data["size"] == 5
    assert data["from"] == 10


async def test_search_endpoint_validation_errors(client):
    response = await client.post("/api/v1/search/", json={"query": ""})
    assert response.status_code == 422

    response = await client.post("/api/v1/search/", json={"query": "test", "size": 0})
    assert response.status_code == 422

    response = await client.post("/api/v1/search/", json={"size": 10})
    assert response.status_code == 422


async def test_search_endpoint_calls_opensearch_with_correct_kwargs(client):
    """Regression test: search.py previously called search_papers(latest_papers=...)
    against a method that only accepts latest=, which raised a TypeError on every
    request. Assert the exact kwargs reaching the client so this can't silently
    come back."""
    response = await client.post(
        "/api/v1/search/",
        json={"query": "graph neural networks", "size": 5, "from": 2, "categories": ["cs.LG"], "latest_papers": True},
    )

    assert response.status_code == 200
    app.state.opensearch_client.search_papers.assert_called_once_with(
        query="graph neural networks", size=5, from_=2, categories=["cs.LG"], latest=True
    )
