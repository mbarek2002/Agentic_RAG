"""Unit tests for Pydantic schemas (no DB/network required)."""

import pytest
from pydantic import ValidationError
from src.schemas.arxiv.paper import ArxivPaper, PaperCreate
from src.schemas.pdf_parser.models import ParsedPaper, ParserType, PdfContent


def test_arxiv_paper_requires_all_fields():
    with pytest.raises(ValidationError):
        ArxivPaper(arxiv_id="2401.00001")


def test_arxiv_paper_accepts_valid_data():
    paper = ArxivPaper(
        arxiv_id="2401.00001",
        title="A Test Paper",
        authors=["Alice", "Bob"],
        abstract="An abstract.",
        categories=["cs.AI"],
        published_date="2024-01-01T00:00:00Z",
        pdf_url="https://arxiv.org/pdf/2401.00001",
    )

    assert paper.arxiv_id == "2401.00001"
    assert paper.authors == ["Alice", "Bob"]


def test_paper_create_pdf_fields_are_optional():
    paper = PaperCreate(
        arxiv_id="2401.00001",
        title="A Test Paper",
        authors=["Alice"],
        abstract="An abstract.",
        categories=["cs.AI"],
        published_date="2024-01-01T00:00:00Z",
        pdf_url="https://arxiv.org/pdf/2401.00001",
    )

    assert paper.raw_text is None
    assert paper.pdf_processed is False


def test_pdf_content_requires_parser_used():
    with pytest.raises(ValidationError):
        PdfContent(raw_text="some text")


def test_pdf_content_defaults_to_empty_collections():
    content = PdfContent(raw_text="some text", parser_used=ParserType.DOCLING)

    assert content.sections == []
    assert content.figures == []
    assert content.tables == []
    assert content.references == []


def test_parsed_paper_combines_metadata_and_content():
    from src.schemas.pdf_parser.models import ArxivMetadata

    metadata = ArxivMetadata(
        title="A Test Paper",
        authors=["Alice"],
        abstract="An abstract.",
        arxiv_id="2401.00001",
        categories=["cs.AI"],
        published_date="2024-01-01T00:00:00Z",
        pdf_url="https://arxiv.org/pdf/2401.00001",
    )
    content = PdfContent(raw_text="some text", parser_used=ParserType.DOCLING)

    parsed = ParsedPaper(arxiv_metadata=metadata, pdf_content=content)

    assert parsed.arxiv_metadata.arxiv_id == "2401.00001"
    assert parsed.pdf_content.raw_text == "some text"
