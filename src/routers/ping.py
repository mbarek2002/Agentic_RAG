from fastapi import APIRouter
from sqlalchemy import text

from ..dependencies import CacheDep, DatabaseDep, LangfuseDep, OpenSearchDep, SettingsDep
from ..schemas.health import HealthResponse, ServiceStatus
from ..services.ollama import OllamaClient

router = APIRouter()


@router.get("/ping", tags=["Health"])
async def ping():
    """Simple ping endpoint for basic connectivity tests."""
    return {"status": "ok", "message": "pong"}


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check the health and status of the API service including database connectivity.",
    response_description="Service health information",
    tags=["Health"],
)
async def health_check(
    settings: SettingsDep,
    database: DatabaseDep,
    opensearch_client: OpenSearchDep,
    cache_client: CacheDep,
    langfuse_tracer: LangfuseDep,
) -> HealthResponse:
    """
    Comprehensive health check endpoint for monitoring and load balancer probes.

    This endpoint provides information about the service health, version,
    environment, and checks connectivity to dependent services like database.

    Returns:
        HealthResponse: Contains service status, version, environment, and service checks

    Example:
        Response:
        ```
        {
            "status": "ok",
            "version": "0.1.0",
            "environment": "development",
            "service_name": "rag-api",
            "services": {
                "database": {"status": "healthy", "message": "Connected successfully"}
            }
        }
        ```
    """
    services = {}
    overall_status = "ok"

    # Test database connectivity
    try:
        with database.get_session() as session:
            # Simple query to test connection
            session.execute(text("SELECT 1"))
            services["database"] = ServiceStatus(status="healthy", message="Connected successfully")
    except Exception as e:
        services["database"] = ServiceStatus(status="unhealthy", message=f"Connection failed: {str(e)}")
        overall_status = "degraded"

    # Test OpenSearch connectivity
    try:
        if not opensearch_client.health_check():
            services["opensearch"] = ServiceStatus(status="unhealthy", message="Not responding")
            overall_status = "degraded"
        else:
            stats = opensearch_client.get_index_stats()
            services["opensearch"] = ServiceStatus(
                status="healthy",
                message=f"Index '{stats.get('index_name', 'unknown')}' with {stats.get('document_count', 0)} documents",
            )
    except Exception as e:
        services["opensearch"] = ServiceStatus(status="unhealthy", message=f"OpenSearch check failed: {str(e)}")
        overall_status = "degraded"

    # Test Ollama service connectivity
    try:
        ollama_client = OllamaClient(settings)
        ollama_health = await ollama_client.health_check()
        services["ollama"] = ServiceStatus(status=ollama_health["status"], message=ollama_health["message"])
        if ollama_health["status"] != "healthy":
            overall_status = "degraded"
    except Exception as e:
        services["ollama"] = ServiceStatus(status="unhealthy", message=f"Ollama check failed: {str(e)}")
        overall_status = "degraded"

    # Test Redis cache connectivity (optional service - never degrades overall status)
    if cache_client is None:
        services["redis"] = ServiceStatus(status="unavailable", message="Cache disabled or unreachable at startup")
    else:
        try:
            cache_client.redis.ping()
            services["redis"] = ServiceStatus(status="healthy", message="Connected successfully")
        except Exception as e:
            services["redis"] = ServiceStatus(status="unhealthy", message=f"Connection failed: {str(e)}")

    # Report Langfuse observability status (optional service - never degrades overall status)
    if langfuse_tracer is not None and langfuse_tracer.client is not None:
        services["langfuse"] = ServiceStatus(status="healthy", message=f"Tracing enabled (host: {langfuse_tracer.settings.host})")
    else:
        services["langfuse"] = ServiceStatus(status="unavailable", message="Tracing disabled or missing credentials")

    return HealthResponse(
        status=overall_status,
        version=settings.app_version,
        environment=settings.environment,
        service_name=settings.service_name,
        services=services,
    )
