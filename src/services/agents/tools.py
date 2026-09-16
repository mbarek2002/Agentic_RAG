import logging
from typing import Tuple

from langchain_core.documents import Document
from langchain_core.tools import tool
from langgraph.runtime import get_runtime

from src.services.embeddings.jina_client import JinaEmbeddingsClient
from src.services.opensearch.client import OpenSearchClient

from .context import Context

logger = logging.getLogger(__name__)


def create_retriever_tool(
    opensearch_client: OpenSearchClient,
    embeddings_client: JinaEmbeddingsClient,
    top_k: int = 3,
    use_hybrid: bool = True,
):
    """Create a retriever tool that wraps OpenSearch service.

    top_k/use_hybrid here are only the fallback used if get_runtime() can't
    find a Context (shouldn't happen in normal graph execution - this tool
    is only ever invoked from inside a compiled graph's ToolNode, which
    always runs with a Context set). The values that actually apply per
    request are runtime.context.top_k/use_hybrid, read fresh on every call -
    see ask()/_run_workflow() in agentic_rag.py, which build a new Context
    per request even though the compiled graph (and this tool closure) are
    built once and cached.

    :param opensearch_client: Existing OpenSearch service
    :param embeddings_client: Existing Jina embeddings service
    :param top_k: Fallback number of chunks to retrieve
    :param use_hybrid: Fallback hybrid search (BM25 + vector) setting
    :returns: LangChain tool for retrieving papers
    """

    @tool(response_format="content_and_artifact")
    async def retrieve_papers(query: str) -> Tuple[str, list[Document]]:
        """Search and return relevant arXiv research papers.

        Use this tool when the user asks about:
        - Machine learning concepts or techniques
        - Deep learning architectures
        - Natural language processing
        - Computer vision methods
        - AI research topics
        - Specific algorithms or models

        :param query: The search query describing what papers to find
        :returns: Tuple of (text content for the LLM, Document list as the
            tool artifact - preserved on the ToolMessage for downstream
            source extraction, since content alone would otherwise be the
            only thing kept once the tool result is turned into a message)
        """
        try:
            runtime = get_runtime(Context)
            request_top_k = runtime.context.top_k
            request_use_hybrid = runtime.context.use_hybrid
        except Exception as e:
            logger.warning(f"get_runtime() failed, falling back to tool-construction-time defaults: {e}")
            request_top_k = top_k
            request_use_hybrid = use_hybrid

        logger.info(f"Retrieving papers for query: {query[:100]}...")
        logger.debug(f"Search mode: {'hybrid' if request_use_hybrid else 'bm25'}, top_k: {request_top_k}")

        # Generate query embedding
        logger.debug("Generating query embedding")
        query_embedding = await embeddings_client.embed_query(query)
        logger.debug(f"Generated embedding with {len(query_embedding)} dimensions")

        # Search using OpenSearch
        logger.debug("Searching OpenSearch")
        search_results = opensearch_client.search_unified(
            query=query,
            query_embedding=query_embedding,
            size=request_top_k,
            use_hybrid=request_use_hybrid,
        )

        # Convert SearchHit to LangChain Document
        documents = []
        hits = search_results.get("hits", [])
        logger.info(f"Found {len(hits)} documents from OpenSearch")

        for hit in hits:
            doc = Document(
                page_content=hit["chunk_text"],
                metadata={
                    "arxiv_id": hit["arxiv_id"],
                    "title": hit.get("title", ""),
                    "authors": hit.get("authors", ""),
                    "score": hit.get("score", 0.0),
                    "source": f"https://arxiv.org/pdf/{hit['arxiv_id']}.pdf",
                    "section": hit.get("section_name", ""),
                    "search_mode": "hybrid" if request_use_hybrid else "bm25",
                    "top_k": request_top_k,
                },
            )
            documents.append(doc)

        logger.debug(f"Converted {len(documents)} hits to LangChain Documents")
        logger.info(f"✓ Retrieved {len(documents)} papers successfully")

        if not documents:
            return "No relevant papers found.", documents

        content = "\n\n".join(f"[arXiv:{doc.metadata.get('arxiv_id', 'unknown')}] {doc.page_content}" for doc in documents)
        return content, documents

    return retrieve_papers
