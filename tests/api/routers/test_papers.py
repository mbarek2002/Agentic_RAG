import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from src.models.paper import Paper


def _make_paper(arxiv_id: str = "2401.00001", title: str = "Test Paper") -> Paper:
    now = datetime.now(timezone.utc)
    return Paper(
        id=uuid.uuid4(),
        arxiv_id=arxiv_id,
        title=title,
        authors=["Jane Doe", "John Smith"],
        abstract="An abstract about machine learning.",
        categories=["cs.AI", "cs.LG"],
        published_date=now,
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
        pdf_processed=False,
        created_at=now,
        updated_at=now,
    )


async def test_list_papers_empty(client):
    with (
        patch("src.repositories.paper.PaperRepository.get_all", return_value=[]),
        patch("src.repositories.paper.PaperRepository.get_count", return_value=0),
    ):
        response = await client.get("/api/v1/papers/")

    assert response.status_code == 200
    data = response.json()
    assert data["papers"] == []
    assert data["total"] == 0


async def test_list_papers_with_results(client):
    papers = [_make_paper("2401.00001", "First Paper"), _make_paper("2401.00002", "Second Paper")]
    with (
        patch("src.repositories.paper.PaperRepository.get_all", return_value=papers),
        patch("src.repositories.paper.PaperRepository.get_count", return_value=2),
    ):
        response = await client.get("/api/v1/papers/?limit=10&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["papers"]) == 2
    assert data["papers"][0]["arxiv_id"] == "2401.00001"
    assert data["papers"][1]["arxiv_id"] == "2401.00002"


async def test_list_papers_pagination_validation(client):
    response = await client.get("/api/v1/papers/?limit=0")
    assert response.status_code == 422

    response = await client.get("/api/v1/papers/?limit=101")
    assert response.status_code == 422

    response = await client.get("/api/v1/papers/?offset=-1")
    assert response.status_code == 422


async def test_get_paper_details_found(client):
    paper = _make_paper("2401.00001", "Found Paper")
    with patch("src.repositories.paper.PaperRepository.get_by_arxiv_id", return_value=paper):
        response = await client.get("/api/v1/papers/2401.00001")

    assert response.status_code == 200
    data = response.json()
    assert data["arxiv_id"] == "2401.00001"
    assert data["title"] == "Found Paper"


async def test_get_paper_details_not_found(client):
    # conftest's default PaperRepository.get_by_arxiv_id mock returns None
    response = await client.get("/api/v1/papers/2401.99999")
    assert response.status_code == 404


async def test_get_paper_details_invalid_id_format(client):
    response = await client.get("/api/v1/papers/not-a-valid-id")
    assert response.status_code == 422
