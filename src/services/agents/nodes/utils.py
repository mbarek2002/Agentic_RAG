import logging
from typing import Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ..models import ReasoningStep, SourceItem, ToolArtefact

logger = logging.getLogger(__name__)


def extract_sources_from_tool_messages(messages: List) -> List[SourceItem]:
    """Extract sources from tool messages in conversation.

    retrieve_papers is defined with response_format="content_and_artifact",
    so its ToolMessage carries the original Document list on `.artifact`
    (the `.content` string alone would lose the structured metadata).

    :param messages: List of messages from graph state
    :returns: List of SourceItem objects, deduplicated by arxiv_id
    """
    sources: List[SourceItem] = []
    seen_arxiv_ids = set()

    for msg in messages:
        if not (isinstance(msg, ToolMessage) and getattr(msg, "name", None) == "retrieve_papers"):
            continue

        documents = getattr(msg, "artifact", None) or []
        for doc in documents:
            metadata = getattr(doc, "metadata", {}) or {}
            arxiv_id = metadata.get("arxiv_id", "")
            if not arxiv_id or arxiv_id in seen_arxiv_ids:
                continue
            seen_arxiv_ids.add(arxiv_id)

            authors_raw = metadata.get("authors", "")
            authors = [a.strip() for a in authors_raw.split(",") if a.strip()] if authors_raw else []

            sources.append(
                SourceItem(
                    arxiv_id=arxiv_id,
                    title=metadata.get("title", ""),
                    authors=authors,
                    url=metadata.get("source", f"https://arxiv.org/pdf/{arxiv_id}.pdf"),
                    relevance_score=metadata.get("score", 0.0),
                )
            )

    return sources


def extract_tool_artefacts(messages: List) -> List[ToolArtefact]:
    """Extract tool artifacts from messages.

    :param messages: List of messages from graph state
    :returns: List of ToolArtefact objects
    """
    artefacts = []

    for msg in messages:
        if isinstance(msg, ToolMessage):
            artefact = ToolArtefact(
                tool_name=getattr(msg, "name", "unknown"),
                tool_call_id=getattr(msg, "tool_call_id", ""),
                content=msg.content,
                metadata={},
            )
            artefacts.append(artefact)

    return artefacts


def create_reasoning_step(
    step_name: str,
    description: str,
    metadata: Optional[Dict] = None,
) -> ReasoningStep:
    """Create a reasoning step record.

    :param step_name: Name of the step/node
    :param description: Human-readable description
    :param metadata: Additional metadata
    :returns: ReasoningStep object
    """
    return ReasoningStep(
        step_name=step_name,
        description=description,
        metadata=metadata or {},
    )


def filter_messages(messages: List) -> List[AIMessage | HumanMessage]:
    """Filter messages to include only HumanMessage and AIMessage types.

    Excludes tool messages and other internal message types.

    :param messages: List of messages to filter
    :returns: Filtered list of messages
    """
    return [msg for msg in messages if isinstance(msg, (HumanMessage, AIMessage))]


def get_latest_query(messages: List) -> str:
    """Get the latest user query from messages.

    :param messages: List of messages
    :returns: Latest query text
    :raises ValueError: If no user query found
    """
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content

    raise ValueError("No user query found in messages")


def get_latest_context(messages: List) -> str:
    """Get the latest context from tool messages.

    :param messages: List of messages
    :returns: Latest context text or empty string
    """
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            return msg.content if hasattr(msg, "content") else ""

    return ""
