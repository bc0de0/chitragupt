"""Document text extraction — PDF, DOCX, plain text.

Returns a flat list of RawPage instances (text + page_number + section_title)
ready for the sliding-window chunker.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RawPage:
    text: str
    page_number: int
    section_title: str | None = None


class DocumentProcessor:
    """Extract text from PDF / DOCX / TXT bytes.

    Falls back gracefully when optional parsing libraries are not installed:
    PDF without pypdf → latin-1 decode; DOCX without python-docx → utf-8 decode.
    """

    def process(self, content: bytes, filename: str) -> list[RawPage]:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext == "pdf":
            return self._extract_pdf(content)
        if ext in ("docx", "doc"):
            return self._extract_docx(content)
        return [RawPage(text=content.decode("utf-8", errors="replace"), page_number=1)]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_pdf(self, content: bytes) -> list[RawPage]:
        try:
            import pypdf
        except ImportError:
            logger.warning("pypdf not installed — decoding PDF bytes as latin-1")
            return [RawPage(text=content.decode("latin-1", errors="replace"), page_number=1)]

        pages: list[RawPage] = []
        reader = pypdf.PdfReader(io.BytesIO(content))
        for i, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(RawPage(text=text, page_number=i))
        return pages or [RawPage(text="", page_number=1)]

    def _extract_docx(self, content: bytes) -> list[RawPage]:
        try:
            import docx  # python-docx
        except ImportError:
            logger.warning("python-docx not installed — decoding DOCX bytes as utf-8")
            return [RawPage(text=content.decode("utf-8", errors="replace"), page_number=1)]

        doc = docx.Document(io.BytesIO(content))
        pages: list[RawPage] = []
        current_section: str | None = None
        buffer: list[str] = []

        def _flush() -> None:
            if buffer:
                pages.append(RawPage(
                    text="\n".join(buffer),
                    page_number=len(pages) + 1,
                    section_title=current_section,
                ))
                buffer.clear()

        for para in doc.paragraphs:
            if para.style.name.startswith("Heading"):
                _flush()
                current_section = para.text.strip() or current_section
            elif para.text.strip():
                buffer.append(para.text)

        _flush()
        return pages or [RawPage(text="", page_number=1)]
