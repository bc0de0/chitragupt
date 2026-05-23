"""Domain 5 — Code Correctness: DocumentProcessor tests.

T-CORR-07, T-CORR-08.

Note: T-EDGE-06, T-EDGE-07, T-EDGE-08 are already covered in test_edge_cases.py.
This file covers correctness tests for the happy-path extraction logic.

All tests run in the 'fast' CI mode — external I/O (pypdf, python-docx) is mocked.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ai_orchestration.ingestion.document_processor import DocumentProcessor, RawPage


# ─────────────────────────────────────────────────────────────────────────────
# T-CORR-07: PDF extraction returns RawPage list with correct page numbers
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
def test_corr_07_pdf_extraction_returns_correct_page_numbers(monkeypatch):
    """
    T-CORR-07: DocumentProcessor._extract_pdf() must return one RawPage per
    non-empty PDF page, with page_number starting at 1 and incrementing.

    EXPECTED: PASS
    """
    import ai_orchestration.ingestion.document_processor as dp_module

    def mock_extract_pdf(self, content: bytes) -> list[RawPage]:
        return [
            RawPage(text="Page one text.", page_number=1),
            RawPage(text="Page two text.", page_number=2),
            RawPage(text="Page three text.", page_number=3),
        ]

    monkeypatch.setattr(dp_module.DocumentProcessor, "_extract_pdf", mock_extract_pdf)

    processor = dp_module.DocumentProcessor()
    pages = processor.process(b"%PDF-1.4 mock content", "report.pdf")

    assert len(pages) == 3
    for expected_num, page in enumerate(pages, start=1):
        assert page.page_number == expected_num, (
            f"Expected page_number={expected_num}, got {page.page_number}"
        )
    assert pages[0].text == "Page one text."
    assert pages[2].text == "Page three text."


@pytest.mark.fast
def test_corr_07b_pdf_skips_empty_pages():
    """
    pypdf returns empty text for image-only pages — the extractor must skip them
    and number the returned pages from pages that have text.
    """
    mock_page_1 = MagicMock()
    mock_page_1.extract_text.return_value = "Real text on page 1."

    mock_page_2 = MagicMock()
    mock_page_2.extract_text.return_value = ""  # image-only page — no text

    mock_page_3 = MagicMock()
    mock_page_3.extract_text.return_value = "  "  # whitespace only → stripped to ""

    mock_page_4 = MagicMock()
    mock_page_4.extract_text.return_value = "Text on page 4."

    mock_reader = MagicMock()
    mock_reader.pages = [mock_page_1, mock_page_2, mock_page_3, mock_page_4]

    mock_pypdf = MagicMock()
    mock_pypdf.PdfReader.return_value = mock_reader

    import ai_orchestration.ingestion.document_processor as dp_module

    with patch.dict("sys.modules", {"pypdf": mock_pypdf}):
        processor = dp_module.DocumentProcessor()
        pages = processor._extract_pdf(b"%PDF-1.4 mock")

    # Only pages 1 and 4 have text; pages 2 and 3 are skipped
    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert pages[0].text == "Real text on page 1."
    assert pages[1].page_number == 4
    assert pages[1].text == "Text on page 4."


@pytest.mark.fast
def test_corr_07c_txt_file_returns_single_page():
    """Plain text files → single RawPage with page_number=1."""
    processor = DocumentProcessor()
    pages = processor.process(b"Hello world. This is a document.", "notes.txt")

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert "Hello world" in pages[0].text


# ─────────────────────────────────────────────────────────────────────────────
# T-CORR-08: DOCX extraction returns paragraphs with section metadata
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
def test_corr_08_docx_extraction_returns_section_metadata():
    """
    T-CORR-08: DocumentProcessor._extract_docx() must group paragraphs under
    their heading and populate section_title on each RawPage.

    EXPECTED: PASS
    """
    # Build a mock python-docx document with headings and body paragraphs
    def make_para(text: str, style_name: str) -> MagicMock:
        p = MagicMock()
        p.text = text
        p.style.name = style_name
        return p

    mock_paragraphs = [
        make_para("Introduction", "Heading 1"),
        make_para("This project aims to improve efficiency.", "Normal"),
        make_para("Background context here.", "Normal"),
        make_para("Scope", "Heading 2"),
        make_para("Only in-scope items are listed below.", "Normal"),
    ]

    mock_doc = MagicMock()
    mock_doc.paragraphs = mock_paragraphs

    mock_docx_mod = MagicMock()
    mock_docx_mod.Document.return_value = mock_doc

    import ai_orchestration.ingestion.document_processor as dp_module

    with patch.dict("sys.modules", {"docx": mock_docx_mod}):
        processor = dp_module.DocumentProcessor()
        pages = processor._extract_docx(b"mock docx bytes")

    # Expect 2 pages: one per heading section
    assert len(pages) == 2, f"Expected 2 section pages, got {len(pages)}: {pages}"

    intro_page = pages[0]
    assert intro_page.section_title == "Introduction"
    assert "improve efficiency" in intro_page.text
    assert "Background context" in intro_page.text

    scope_page = pages[1]
    assert scope_page.section_title == "Scope"
    assert "in-scope" in scope_page.text


@pytest.mark.fast
def test_corr_08b_docx_no_headings_returns_single_page():
    """A DOCX without any Heading styles produces a single page with no section_title."""
    def make_para(text: str) -> MagicMock:
        p = MagicMock()
        p.text = text
        p.style.name = "Normal"
        return p

    mock_doc = MagicMock()
    mock_doc.paragraphs = [
        make_para("First paragraph."),
        make_para("Second paragraph."),
    ]

    mock_docx_mod = MagicMock()
    mock_docx_mod.Document.return_value = mock_doc

    import ai_orchestration.ingestion.document_processor as dp_module

    with patch.dict("sys.modules", {"docx": mock_docx_mod}):
        processor = dp_module.DocumentProcessor()
        pages = processor._extract_docx(b"mock docx bytes")

    assert len(pages) == 1
    assert pages[0].section_title is None
    assert "First paragraph." in pages[0].text
    assert "Second paragraph." in pages[0].text


@pytest.mark.fast
def test_corr_08c_docx_empty_document_returns_placeholder():
    """An empty DOCX (no paragraphs) returns a single placeholder RawPage."""
    mock_doc = MagicMock()
    mock_doc.paragraphs = []

    mock_docx_mod = MagicMock()
    mock_docx_mod.Document.return_value = mock_doc

    import ai_orchestration.ingestion.document_processor as dp_module

    with patch.dict("sys.modules", {"docx": mock_docx_mod}):
        processor = dp_module.DocumentProcessor()
        pages = processor._extract_docx(b"mock docx bytes")

    assert len(pages) == 1
    assert pages[0].page_number == 1
