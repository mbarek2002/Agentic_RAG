"""OpenSearch hybrid indexing tasks (chunking + embeddings + kNN) for the arXiv ingestion DAG."""

import asyncio
import logging
import sys

# Add project root to Python path for imports (mirrors tasks.py - the DAG
# file may import this module before tasks.py has run its own sys.path setup)
sys.path.insert(0, "/opt/airflow")

from arxiv_ingestion.tasks import get_cached_services  # noqa: E402
from sqlalchemy import text  # noqa: E402
from src.repositories.paper import PaperRepository  # noqa: E402
from src.services.indexing.factory import make_hybrid_indexing_service  # noqa: E402

logger = logging.getLogger(__name__)


def index_papers_hybrid(**context):
    """
    Chunk, embed, and index today's papers into the hybrid OpenSearch index.

    Queries papers stored today directly from PostgreSQL (not just the ones
    fetched by this run, so re-running indexing alone still works), then
    delegates chunking + embedding + bulk indexing to HybridIndexingService.
    """
    logger.info("Indexing today's papers to the hybrid OpenSearch index")

    try:
        _arxiv_client, _pdf_parser, database, _metadata_fetcher, opensearch_client = get_cached_services()

        if not opensearch_client.health_check():
            logger.error("OpenSearch is not healthy, skipping indexing")
            return {"status": "failed", "message": "OpenSearch not healthy", "papers_indexed": 0}

        hybrid_indexer = make_hybrid_indexing_service()

        with database.get_session() as session:
            paper_repo = PaperRepository(session)
            todays_ids = session.execute(text("SELECT id FROM papers WHERE DATE(created_at) = CURRENT_DATE")).fetchall()

            papers_data = []
            for (paper_id,) in todays_ids:
                paper = paper_repo.get_by_id(paper_id)
                if not paper:
                    continue

                papers_data.append(
                    {
                        "id": str(paper.id),
                        "arxiv_id": paper.arxiv_id,
                        "title": paper.title,
                        "authors": paper.authors,
                        "abstract": paper.abstract,
                        "categories": paper.categories,
                        "published_date": paper.published_date.isoformat() if paper.published_date else None,
                        "raw_text": paper.raw_text or "",
                        "sections": paper.sections,
                    }
                )

        if not papers_data:
            logger.info("No papers found for today, nothing to index")
            return {"status": "success", "papers_indexed": 0, "total_chunks_indexed": 0, "message": "No papers to index"}

        stats = asyncio.run(hybrid_indexer.index_papers_batch(papers_data, replace_existing=True))

        logger.info(
            f"Hybrid indexing complete: {stats['papers_processed']} papers, "
            f"{stats['total_chunks_indexed']} chunks indexed, {stats['total_errors']} errors"
        )

        return {
            "status": "success",
            "papers_indexed": stats["papers_processed"],
            "total_chunks_created": stats["total_chunks_created"],
            "total_chunks_indexed": stats["total_chunks_indexed"],
            "total_embeddings_generated": stats["total_embeddings_generated"],
            "papers_failed": stats["total_errors"],
            "message": f"{stats['papers_processed']} papers indexed ({stats['total_chunks_indexed']} chunks)",
        }

    except Exception as e:
        error_msg = f"Hybrid OpenSearch indexing failed: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


def verify_hybrid_index(**context):
    """
    Verify the hybrid index after indexing: total chunks, unique papers, index size.

    Unique paper count is computed via a cardinality aggregation on the
    (keyword-mapped) arxiv_id field, since each paper is split across
    multiple chunk documents.
    """
    logger.info("Verifying hybrid OpenSearch index")

    try:
        _arxiv_client, _pdf_parser, _database, _metadata_fetcher, opensearch_client = get_cached_services()

        stats = opensearch_client.get_index_stats()

        unique_papers = 0
        try:
            agg_response = opensearch_client.client.search(
                index=opensearch_client.index_name,
                body={"size": 0, "aggs": {"unique_papers": {"cardinality": {"field": "arxiv_id"}}}},
            )
            unique_papers = agg_response["aggregations"]["unique_papers"]["value"]
        except Exception as e:
            logger.warning(f"Could not compute unique paper count: {e}")

        result = {
            "status": "success",
            "index_name": stats.get("index_name"),
            "total_chunks": stats.get("document_count", 0),
            "unique_papers": unique_papers,
            "size_in_bytes": stats.get("size_in_bytes", 0),
        }

        logger.info(
            f"Hybrid index verification: {result['total_chunks']} chunks across "
            f"{result['unique_papers']} unique papers ({result['size_in_bytes']} bytes)"
        )

        return result

    except Exception as e:
        error_msg = f"Hybrid index verification failed: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
