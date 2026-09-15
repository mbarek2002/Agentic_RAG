from typing import Optional

from pydantic import BaseModel


class ChunkMetadata(BaseModel):
    """Metadata describing where a chunk sits within its source paper."""

    chunk_index: int
    start_char: int
    end_char: int
    word_count: int
    overlap_with_previous: int = 0
    overlap_with_next: int = 0
    section_title: Optional[str] = None


class TextChunk(BaseModel):
    """A single chunk of a paper's text, ready for embedding and indexing."""

    text: str
    metadata: ChunkMetadata
    arxiv_id: str
    paper_id: str
