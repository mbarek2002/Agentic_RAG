import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from src.config import get_settings
from src.db.factory import make_database
from src.routers import hybrid_search, papers, ping, ask, search
from src.services.arxiv.factory import make_arxiv_client
from src.services.cache.factory import make_cache_client
from src.services.embeddings.factory import make_embeddings_service
from src.services.langfuse.factory import make_langfuse_tracer
from src.services.ollama.factory import make_ollama_client
from src.services.opensearch.factory import make_opensearch_client
from src.services.pdf_parser.factory import make_pdf_parser_service

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan for the API.
    """
    logger.info("Starting RAG API...")

    settings = get_settings()
    app.state.settings = settings

    database = make_database()
    app.state.database = database
    logger.info("Database connected")

    # Initialize services (kept for future endpoints and notebook demos)
    app.state.arxiv_client = make_arxiv_client()
    app.state.pdf_parser = make_pdf_parser_service()
    logger.info("Services initialized: arXiv API client, PDF parser")

    opensearch_client = make_opensearch_client()
    app.state.opensearch_client = opensearch_client
    if opensearch_client.health_check():
        setup_results = opensearch_client.setup_indices(force=False)
        if setup_results.get("hybrid_index"):
            logger.info("OpenSearch hybrid index created")
        if setup_results.get("rrf_pipeline"):
            logger.info("OpenSearch RRF pipeline created")
        stats = opensearch_client.get_index_stats()
        logger.info(f"OpenSearch index '{opensearch_client.index_name}': {stats.get('document_count', 0)} documents")
    else:
        logger.warning("OpenSearch is not reachable at startup - /hybrid-search will report 503 until it recovers")

    app.state.embeddings_service = make_embeddings_service()
    logger.info("Embeddings service initialized (Jina AI)")

    app.state.ollama_client = make_ollama_client()
    logger.info("Ollama client initialized")

    app.state.langfuse_tracer = make_langfuse_tracer()
    logger.info("Langfuse tracer initialized (no-op if disabled/unconfigured)")

    try:
        app.state.cache_client = make_cache_client(settings)
        logger.info("Redis cache client initialized")
    except Exception as e:
        app.state.cache_client = None
        logger.warning(f"Redis cache unavailable, continuing without caching: {e}")

    logger.info("API ready")
    yield

    # Cleanup
    app.state.langfuse_tracer.shutdown()
    database.teardown()
    logger.info("API shutdown complete")


app = FastAPI(
    title="arXiv Paper Curator API",
    description="Personal arXiv CS.AI paper curator with RAG capabilities",
    version=os.getenv("APP_VERSION", "0.1.0"),
    lifespan=lifespan,
)

# Include routers
app.include_router(ping.router, prefix="/api/v1")
app.include_router(papers.router, prefix="/api/v1")
app.include_router(hybrid_search.router, prefix="/api/v1")
app.include_router(ask.ask_router, prefix="/api/v1")
app.include_router(ask.stream_router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")

if __name__ == "__main__":
    uvicorn.run(app, port=8000, host="0.0.0.0")
