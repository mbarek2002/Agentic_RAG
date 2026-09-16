from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from src.main import app


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Async backend for testing."""
    return "asyncio"


@pytest.fixture
async def client():
    """HTTP client for API testing with mocked services."""
    # Mock database startup and session to prevent real connections
    # Patched at "src.main.make_X" (where main.py's lifespan calls them via its
    # own `from ... import make_X` binding) rather than at the factory modules
    # they're defined in - patching the definition site doesn't affect a name
    # already bound into another module's namespace via `from x import y`.
    with (
        patch("src.db.interfaces.postgresql.PostgreSQLDatabase.startup") as mock_startup,
        patch("src.db.interfaces.postgresql.PostgreSQLDatabase.get_session") as mock_get_session,
        patch("src.main.make_opensearch_client") as mock_os,
        patch("src.main.make_arxiv_client") as mock_arxiv,
        patch("src.main.make_pdf_parser_service") as mock_pdf,
        patch("src.main.make_embeddings_service") as mock_embeddings,
        patch("src.main.make_ollama_client") as mock_ollama,
        patch("src.main.make_langfuse_tracer") as mock_langfuse,
        patch("src.main.make_cache_client") as mock_cache,
        patch("src.repositories.paper.PaperRepository.get_by_arxiv_id") as mock_get_by_id,
    ):
        # Mock startup to do nothing
        mock_startup.return_value = None

        # Mock get_session to return a mock session
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_get_session.return_value.__exit__.return_value = None

        # Mock repository methods to return None (not found) by default
        mock_get_by_id.return_value = None

        # Set up other mock return values
        # OpenSearchClient's methods are all synchronous - a bare AsyncMock's
        # unconfigured children return MagicMocks, so `.get("total", 0)` etc.
        # would hand Pydantic a MagicMock instead of an int/list and 500 every
        # search request. Use a MagicMock with realistic dict/bool returns.
        mock_opensearch = MagicMock()
        mock_opensearch.health_check.return_value = True
        mock_opensearch.setup_indices.return_value = {"hybrid_index": False, "rrf_pipeline": False}
        mock_opensearch.get_index_stats.return_value = {"index_name": "test-index", "document_count": 0}
        mock_opensearch.search_unified.return_value = {"hits": [], "total": 0}
        mock_opensearch.search_papers.return_value = {"hits": [], "total": 0}
        mock_os.return_value = mock_opensearch

        mock_arxiv.return_value = AsyncMock()
        mock_pdf.return_value = AsyncMock()
        mock_embeddings.return_value = AsyncMock()
        mock_ollama.return_value = AsyncMock()
        mock_langfuse.return_value = MagicMock()
        # No real Redis in tests - simulate cache disabled/unreachable (matches
        # the app's own graceful-degradation fallback in main.py's lifespan)
        mock_cache.return_value = None

        async with LifespanManager(app) as manager:
            async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
                yield client
