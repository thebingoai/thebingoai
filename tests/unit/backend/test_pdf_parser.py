"""Tests for the PDF parser extract_text utility."""

import sys
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Ensure PyPDF2 is available (stub it if not installed locally)
# ---------------------------------------------------------------------------
_PyPDF2_installed = "PyPDF2" in sys.modules or True
try:
    import PyPDF2 as _real_pypdf2  # noqa: F401
except ModuleNotFoundError:
    _fake_pypdf2 = MagicMock()
    sys.modules["PyPDF2"] = _fake_pypdf2
    _PyPDF2_installed = False

from backend.parser.pdf import extract_text  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_page(text: str):
    """Create a mock PDF page with extract_text returning *text*."""
    page = MagicMock()
    page.extract_text.return_value = text
    return page


def _patch_reader(pages):
    """Return a context-manager-style patch that replaces PdfReader."""
    from unittest.mock import patch

    reader = MagicMock()
    reader.pages = pages
    return patch("backend.parser.pdf.PyPDF2.PdfReader", return_value=reader)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPDFParser:
    """Tests for PDF parsing with mocked PyPDF2.PdfReader."""

    def test_single_page_pdf(self):
        """A single-page PDF returns its text and page_count=1."""
        with _patch_reader([_fake_page("Hello PDF")]):
            result = extract_text(b"fake-pdf-bytes")

        assert result["text"] == "Hello PDF"
        assert result["page_count"] == 1

    def test_multi_page_pdf(self):
        """Multiple pages are joined with double newlines."""
        with _patch_reader([_fake_page("Page one"), _fake_page("Page two")]):
            result = extract_text(b"fake-pdf-bytes")

        assert "Page one" in result["text"]
        assert "Page two" in result["text"]
        assert result["page_count"] == 2

    def test_empty_pdf(self):
        """A PDF with zero pages returns empty text and page_count=0."""
        with _patch_reader([]):
            result = extract_text(b"fake-pdf-bytes")

        assert result["text"] == ""
        assert result["page_count"] == 0

    def test_page_extraction_failure_graceful(self):
        """If a page raises during extract_text, it is logged and treated as empty."""
        bad_page = MagicMock()
        bad_page.extract_text.side_effect = RuntimeError("corrupt page")

        with _patch_reader([_fake_page("Good page"), bad_page]):
            result = extract_text(b"fake-pdf-bytes")

        assert result["page_count"] == 2
        assert "Good page" in result["text"]

    def test_return_structure_keys(self):
        """Returned dict has exactly the expected keys."""
        with _patch_reader([_fake_page("text")]):
            result = extract_text(b"fake-pdf-bytes")

        assert set(result.keys()) == {"text", "page_count"}
