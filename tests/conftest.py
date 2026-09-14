"""Main test configuration and fixtures."""

import pytest
from polyfactory.factories.pydantic_factory import ModelFactory
from src.config import Settings
from src.schemas.arxiv.paper import PaperCreate, PaperResponse


@pytest.fixture
def settings() -> Settings:
    """Test settings fixture."""
    return Settings()


class PaperCreateFactory(ModelFactory[PaperCreate]): ...


class PaperResponseFactory(ModelFactory[PaperResponse]): ...


@pytest.fixture
def paper_create_data() -> PaperCreate:
    """Mock paper creation data."""
    return PaperCreateFactory.build()


@pytest.fixture
def paper_response_data() -> PaperResponse:
    """Mock paper response data."""
    return PaperResponseFactory.build()
