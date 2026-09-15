import asyncio
import logging
import sys
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Tuple

# Add project root to Python path for imports
sys.path.insert(0, "/opt/airflow")

# All imports at the top
from sqlalchemy import text
from src.db.factory import make_database
from src.repositories.paper import PaperRepository
from src.services.arxiv.factory import make_arxiv_client
from src.services.metadata_fetcher import make_metadata_fetcher
from src.services.opensearch.factory import make_opensearch_client
from src.services.pdf_parser.factory import make_pdf_parser_service

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_cached_services() -> Tuple[Any, Any, Any, Any, Any]:
    """
    Get cached service instances using lru_cache for automatic memoization.

    Returns:
        Tuple of (arxiv_client, pdf_parser, database, metadata_fetcher, opensearch_client)
    """
    logger.info("Initializing services (cached with lru_cache)")

    # Initialize core services
    arxiv_client = make_arxiv_client()
    pdf_parser = make_pdf_parser_service()
    database = make_database()
    opensearch_client = make_opensearch_client()

    # Create metadata fetcher with dependencies (hybrid indexing is done by a
    # separate Airflow task against Postgres, not through MetadataFetcher here)
    metadata_fetcher = make_metadata_fetcher(arxiv_client, pdf_parser)

    logger.info("All services initialized and cached with lru_cache")
    return arxiv_client, pdf_parser, database, metadata_fetcher, opensearch_client


async def run_paper_ingestion_pipeline(
    target_date: str,
    max_results: int = 5,
    process_pdfs: bool = True,
) -> dict:
    """
    Async wrapper for the paper ingestion pipeline.

    Args:
        target_date: Date to fetch papers for (YYYYMMDD format)
        max_results: Maximum number of papers to fetch
        process_pdfs: Whether to process PDFs

    Returns:
        Dictionary with processing results
    """
    _arxiv_client, _pdf_parser, database, metadata_fetcher, _opensearch_client = get_cached_services()

    with database.get_session() as session:
        return await metadata_fetcher.fetch_and_process_papers(
            max_results=max_results,
            from_date=target_date,
            to_date=target_date,
            process_pdfs=process_pdfs,
            store_to_db=True,
            db_session=session,
        )


def setup_environment():
    """Setup environment and verify dependencies."""
    logger.info("Setting up environment for arXiv paper ingestion")

    try:
        # Get cached services (initialized once)
        arxiv_client, _pdf_parser, database, _metadata_fetcher, _opensearch_client = get_cached_services()

        # Test database connection
        with database.get_session() as session:
            session.execute(text("SELECT 1"))
            logger.info("Database connection verified")

        logger.info(f"arXiv client ready: {arxiv_client.base_url}")
        logger.info("PDF parser service ready (Docling models cached)")

        return {"status": "success", "message": "Environment setup completed"}

    except Exception as e:
        error_msg = f"Environment setup failed: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


def fetch_daily_papers(**context):
    """
    Fetch CS.AI papers from the last 24 hours.

    This function:
    1. Calculates the date range for yesterday
    2. Fetches papers using the MetadataFetcher
    3. Returns processing statistics
    """
    logger.info("Starting daily arXiv paper fetch")

    try:
        # Calculate date range (yesterday - execution_date - 1)
        execution_date = context["ds"]  # YYYY-MM-DD format
        execution_dt = datetime.strptime(execution_date, "%Y-%m-%d")
        target_dt = execution_dt - timedelta(days=1)  # Get papers from day before
        target_date = target_dt.strftime("%Y%m%d")

        logger.info(f"Fetching papers for date: {target_date}")

        # Execute paper ingestion pipeline
        results = asyncio.run(
            run_paper_ingestion_pipeline(
                target_date=target_date,
                max_results=10,
                process_pdfs=True,
            )
        )
        logger.info(f"Daily paper fetch completed: {results}")

        # Store results for downstream tasks
        context["task_instance"].xcom_push(key="fetch_results", value=results)

        return results

    except Exception as e:
        error_msg = f"Daily paper fetch failed: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


def index_papers_to_opensearch(**context):
    """
    Index today's papers from PostgreSQL into OpenSearch for BM25 search.

    This function:
    1. Queries papers stored today directly from PostgreSQL (not just the
       ones fetched by this run, so re-running indexing alone still works)
    2. Builds an OpenSearch document per paper (raw_text included as-is;
       MetadataFetcher already truncates it to opensearch.max_text_size
       when it was stored)
    3. Indexes each document via OpenSearchClient.index_paper()
    """
    logger.info("Indexing today's papers to OpenSearch")

    try:
        _arxiv_client, _pdf_parser, database, _metadata_fetcher, opensearch_client = get_cached_services()

        if not opensearch_client.health_check():
            logger.error("OpenSearch is not healthy, skipping indexing")
            return {"status": "failed", "message": "OpenSearch not healthy", "papers_indexed": 0}

        indexed_count = 0
        failed_count = 0

        with database.get_session() as session:
            paper_repo = PaperRepository(session)

            todays_ids = session.execute(text("SELECT id FROM papers WHERE DATE(created_at) = CURRENT_DATE")).fetchall()

            for (paper_id,) in todays_ids:
                paper = paper_repo.get_by_id(paper_id)
                if not paper:
                    continue

                paper_doc = {
                    "arxiv_id": paper.arxiv_id,
                    "title": paper.title,
                    "authors": paper.authors,
                    "abstract": paper.abstract,
                    "categories": paper.categories,
                    "pdf_url": paper.pdf_url,
                    "published_date": paper.published_date.isoformat() if paper.published_date else None,
                    "raw_text": paper.raw_text or "",
                }

                if opensearch_client.index_paper(paper_doc):
                    indexed_count += 1
                else:
                    failed_count += 1
                    logger.warning(f"Failed to index paper {paper.arxiv_id} to OpenSearch")

        logger.info(f"OpenSearch indexing complete: {indexed_count} indexed, {failed_count} failed")

        return {
            "status": "success",
            "papers_indexed": indexed_count,
            "papers_failed": failed_count,
            "message": f"{indexed_count} papers indexed to OpenSearch",
        }

    except Exception as e:
        error_msg = f"OpenSearch indexing failed: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


def generate_daily_report(**context):
    """
    Generate a daily processing report.

    This function:
    1. Collects results from all tasks
    2. Generates summary statistics
    3. Logs the daily report
    """
    logger.info("Generating daily processing report")

    try:
        fetch_results = context["task_instance"].xcom_pull(task_ids="fetch_daily_papers", key="fetch_results")

        opensearch_results = context["task_instance"].xcom_pull(task_ids="index_papers_to_opensearch")

        report = {
            "date": context["ds"],
            "execution_time": datetime.now().isoformat(),
            "papers": {
                "fetched": fetch_results.get("papers_fetched", 0) if fetch_results else 0,
                "pdfs_downloaded": fetch_results.get("pdfs_downloaded", 0) if fetch_results else 0,
                "pdfs_parsed": fetch_results.get("pdfs_parsed", 0) if fetch_results else 0,
                "stored": fetch_results.get("papers_stored", 0) if fetch_results else 0,
            },
            "processing": {
                "processing_time_seconds": fetch_results.get("processing_time", 0) if fetch_results else 0,
                "errors": len(fetch_results.get("errors", [])) if fetch_results else 0,
            },
            "opensearch": {
                "papers_indexed": opensearch_results.get("papers_indexed", 0) if opensearch_results else 0,
                "papers_failed": opensearch_results.get("papers_failed", 0) if opensearch_results else 0,
                "status": opensearch_results.get("status", "unknown") if opensearch_results else "unknown",
            },
        }

        logger.info("=== DAILY ARXIV PROCESSING REPORT ===")
        logger.info(f"Date: {report['date']}")
        logger.info(f"Papers fetched: {report['papers']['fetched']}")
        logger.info(f"PDFs downloaded: {report['papers']['pdfs_downloaded']}")
        logger.info(f"PDFs parsed: {report['papers']['pdfs_parsed']}")
        logger.info(f"Papers stored: {report['papers']['stored']}")
        logger.info(f"Processing time: {report['processing']['processing_time_seconds']:.1f}s")
        logger.info(f"Errors encountered: {report['processing']['errors']}")
        logger.info(f"Papers indexed to OpenSearch: {report['opensearch']['papers_indexed']}")
        logger.info("=== END REPORT ===")

        return report

    except Exception as e:
        error_msg = f"Report generation failed: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
