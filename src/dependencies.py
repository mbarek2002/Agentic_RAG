from functools import lru_cache
from typing import Annotated, Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session
from src.config import Settings
from src.db.interfaces.base import BaseDatabase
from src.services.agents.agentic_rag import AgenticRAGService
from src.services.agents.factory import make_agentic_rag_service
from src.services.arxiv.client import ArxivClient
from src.services.cache.client import CacheClient
from src.services.embeddings.jina_client import JinaEmbeddingsClient
from src.services.langfuse.client import LangfuseTracer
from src.services.ollama.client import OllamaClient
from src.services.opensearch.client import OpenSearchClient
from src.services.pdf_parser.parser import PDFParserService


@lru_cache
def get_settings() -> Settings:
    """Get application settings."""
    return Settings()


def get_request_settings(request: Request) -> Settings:
    """Get settings from the request state."""
    return request.app.state.settings


def get_database(request: Request) -> BaseDatabase:
    """Get database from the request state."""
    return request.app.state.database


def get_db_session(database: Annotated[BaseDatabase, Depends(get_database)]) -> Generator[Session, None, None]:
    """Get database session dependency."""
    with database.get_session() as session:
        yield session


def get_opensearch_client(request: Request) -> OpenSearchClient:
    """Get OpenSearch client from the request state."""
    return request.app.state.opensearch_client


def get_arxiv_client(request: Request) -> ArxivClient:
    """Get arXiv client from the request state."""
    return request.app.state.arxiv_client


def get_pdf_parser(request: Request) -> PDFParserService:
    """Get PDF parser service from the request state."""
    return request.app.state.pdf_parser


def get_embeddings_service(request: Request) -> JinaEmbeddingsClient:
    """Get embeddings service from the request state."""
    return request.app.state.embeddings_service


def get_langfuse_tracer(request: Request) -> LangfuseTracer | None:
    """Get Langfuse tracer from the request state."""
    return getattr(request.app.state, "langfuse_tracer", None)


def get_cache_client(request: Request) -> CacheClient | None:
    """Get cache client from the request state."""
    return getattr(request.app.state, "cache_client", None)


def get_ollama_client(request: Request) -> OllamaClient:
    """Get Ollama client from the request state."""
    return request.app.state.ollama_client


# Dependency annotations
SettingsDep = Annotated[Settings, Depends(get_settings)]
DatabaseDep = Annotated[BaseDatabase, Depends(get_database)]
SessionDep = Annotated[Session, Depends(get_db_session)]
OpenSearchDep = Annotated[OpenSearchClient, Depends(get_opensearch_client)]
ArxivDep = Annotated[ArxivClient, Depends(get_arxiv_client)]
PDFParserDep = Annotated[PDFParserService, Depends(get_pdf_parser)]
EmbeddingsDep = Annotated[JinaEmbeddingsClient, Depends(get_embeddings_service)]
LangfuseDep = Annotated[LangfuseTracer | None, Depends(get_langfuse_tracer)]
CacheDep = Annotated[CacheClient | None, Depends(get_cache_client)]
OllamaDep = Annotated[OllamaClient, Depends(get_ollama_client)]


@lru_cache(maxsize=1)
def _build_agentic_rag_service(
    opensearch: OpenSearchClient,
    ollama: OllamaClient,
    embeddings: JinaEmbeddingsClient,
    langfuse: LangfuseTracer | None,
    model: str,
) -> AgenticRAGService:
    """Build the agentic RAG service once and cache it.

    Unlike the other Dep factories here (which just proxy app.state
    singletons built in main.py's lifespan), AgenticRAGService compiles a
    LangGraph workflow in its constructor - not something to redo on every
    request. The args above are the same app.state singleton instances on
    every call, so this lru_cache hits from the second request onward.
    """
    return make_agentic_rag_service(
        opensearch_client=opensearch,
        ollama_client=ollama,
        embeddings_client=embeddings,
        langfuse_tracer=langfuse,
        model=model,
    )


def get_agentic_rag_service(
    opensearch: OpenSearchDep,
    ollama: OllamaDep,
    embeddings: EmbeddingsDep,
    langfuse: LangfuseDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AgenticRAGService:
    """Get agentic RAG service."""
    return _build_agentic_rag_service(opensearch, ollama, embeddings, langfuse, settings.ollama_default_model)


AgenticRAGDep = Annotated[AgenticRAGService, Depends(get_agentic_rag_service)]
