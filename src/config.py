from typing import Annotated, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class DefaultSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        frozen=True,
        env_nested_delimiter="__",
    )


class ArxivSettings(DefaultSettings):
    """arXiv API client settings."""

    base_url: str = "https://export.arxiv.org/api/query"
    namespaces: dict = Field(
        default={
            "atom": "http://www.w3.org/2005/Atom",
            "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
    )
    pdf_cache_dir: str = "./data/arxiv_pdfs"
    rate_limit_delay: float = 3.0  # seconds between requests
    timeout_seconds: int = 30
    max_results: int = 100
    search_category: str = "cs.AI"  # Default category to search

    # PDF download tuning (used by MetadataFetcher's batch pipeline)
    download_max_retries: int = 3
    download_retry_delay_base: float = 5.0  # seconds, multiplied by attempt number
    max_concurrent_downloads: int = 5
    max_concurrent_parsing: int = 1


class PDFParserSettings(DefaultSettings):
    """PDF parser service settings."""

    max_pages: int = 30
    max_file_size_mb: int = 20
    do_ocr: bool = False
    do_table_structure: bool = True


class OpenSearchSettings(DefaultSettings):
    """OpenSearch client and index settings."""

    host: str = "http://localhost:9200"
    index_name: str = "arxiv-papers"
    max_text_size: int = 1_000_000  # characters of raw_text indexed per document

    # Hybrid search (chunk-level index + kNN vectors + RRF)
    chunk_index_suffix: str = "chunks"
    vector_dimension: int = 1024  # matches Jina embeddings-v3 output size
    vector_space_type: str = "cosinesimil"
    rrf_pipeline_name: str = "hybrid-rrf-pipeline"
    hybrid_search_size_multiplier: int = 3  # over-fetch per query before RRF fusion


class ChunkingSettings(DefaultSettings):
    """Text chunking settings for hybrid indexing."""

    chunk_size: int = 600
    overlap_size: int = 100
    min_chunk_size: int = 100
    section_based: bool = True


class LangfuseSettings(DefaultSettings):

    public_key: str = ""
    secret_key: str = ""
    host: str = "http://localhost:3000"  # Self-hosted Langfuse URL
    enabled: bool = True
    flush_at: int = 15  # Number of events before flushing
    flush_interval: float = 1.0  # Seconds between flushes
    max_retries: int = 3
    timeout: int = 30
    debug: bool = False


class RedisSettings(DefaultSettings):

    host: str = "localhost"
    port: int = 6379
    password: str = ""
    db: int = 0
    decode_responses: bool = True
    socket_timeout: int = 30
    socket_connect_timeout: int = 30

    # Cache settings
    ttl_hours: int = 6  # Cache TTL in hours



class Settings(DefaultSettings):
    """Application settings."""

    app_version: str = "0.1.0"
    debug: bool = True
    environment: str = "development"
    service_name: str = "rag-api"

    # PostgreSQL configuration
    postgres_database_url: str = "postgresql://rag_user:rag_password@localhost:5432/rag_db"
    postgres_echo_sql: bool = False
    postgres_pool_size: int = 20
    postgres_max_overflow: int = 0

    # Ollama configuration (used in Week 1 notebook)
    ollama_host: str = "http://localhost:11434"
    ollama_models: Annotated[List[str], NoDecode] = Field(default=["gemma3:4b", "mistral:latest"])
    ollama_default_model: str = "llama3.2:1b"
    ollama_timeout: int = 300  # 5 minutes for LLM operations

    # arXiv settings
    arxiv: ArxivSettings = Field(default_factory=ArxivSettings)

    # PDF parser settings
    pdf_parser: PDFParserSettings = Field(default_factory=PDFParserSettings)

    # OpenSearch settings
    opensearch: OpenSearchSettings = Field(default_factory=OpenSearchSettings)

    # Chunking settings
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)

    # Jina AI embeddings API key (get one at https://jina.ai) - required for hybrid search
    jina_api_key: str = ""

    # Langfuse observability settings
    langfuse: LangfuseSettings = Field(default_factory=LangfuseSettings)

    # Redis cache settings
    redis: RedisSettings = Field(default_factory=RedisSettings)

    @field_validator("ollama_models", mode="before")
    @classmethod
    def parse_ollama_models(cls, v):
        """Parse comma-separated string into list of models."""
        if isinstance(v, str):
            return [model.strip() for model in v.split(",") if model.strip()]
        return v

    @field_validator("postgres_database_url")
    @classmethod
    def validate_postgres_url(cls, v: str) -> str:
        """Reject obviously wrong connection strings early instead of failing deep inside SQLAlchemy."""
        if not v.startswith(("postgresql://", "postgresql+psycopg2://")):
            raise ValueError(
                f"postgres_database_url must start with 'postgresql://' or 'postgresql+psycopg2://', got: {v!r}"
            )
        return v


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
