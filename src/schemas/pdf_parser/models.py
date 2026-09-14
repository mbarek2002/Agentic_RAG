from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ParserType(str, Enum):
    """Which parser produced a PdfContent instance."""

    DOCLING = "docling"


class PaperSection(BaseModel):
    """A titled section of extracted PDF text."""

    title: str
    content: str


class PaperFigure(BaseModel):
    """A figure extracted from a PDF (currently unused, kept for schema stability)."""

    caption: Optional[str] = None
    page: Optional[int] = None


class PaperTable(BaseModel):
    """A table extracted from a PDF (currently unused, kept for schema stability)."""

    caption: Optional[str] = None
    page: Optional[int] = None


class PdfContent(BaseModel):
    """Structured content extracted from a parsed PDF."""

    sections: List[PaperSection] = Field(default_factory=list)
    figures: List[PaperFigure] = Field(default_factory=list)
    tables: List[PaperTable] = Field(default_factory=list)
    raw_text: str = ""
    references: List[str] = Field(default_factory=list)
    parser_used: ParserType
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ArxivMetadata(BaseModel):
    """arXiv metadata for a paper, decoupled from the arxiv service's own schema."""

    title: str
    authors: List[str]
    abstract: str
    arxiv_id: str
    categories: List[str]
    published_date: str
    pdf_url: str


class ParsedPaper(BaseModel):
    """A paper's arXiv metadata combined with its parsed PDF content."""

    arxiv_metadata: ArxivMetadata
    pdf_content: PdfContent
