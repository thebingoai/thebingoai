"""Tests for the DOCX parser extract_text utility."""

import sys
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Ensure python-docx is available (stub it if not installed locally)
# ---------------------------------------------------------------------------
try:
    import docx as _real_docx  # noqa: F401
except ModuleNotFoundError:
    _fake_docx = MagicMock()
    sys.modules["docx"] = _fake_docx

from backend.parser.docx_parser import extract_text  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_paragraph(text: str):
    """Create a mock paragraph with a .text attribute."""
    p = MagicMock()
    p.text = text
    return p


def _patch_document(paragraphs):
    """Return a context-manager patch that replaces docx.Document."""
    from unittest.mock import patch

    doc = MagicMock()
    doc.paragraphs = paragraphs
    return patch("backend.parser.docx_parser.docx.Document", return_value=doc)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDocxParser:
    """Tests for DOCX parsing with mocked docx.Document."""

    def test_simple_document(self):
        """A document with two paragraphs returns joined text."""
        with _patch_document([_fake_paragraph("First paragraph"), _fake_paragraph("Second paragraph")]):
            result = extract_text(b"fake-docx-bytes")

        assert "First paragraph" in result["text"]
        assert "Second paragraph" in result["text"]
        assert result["paragraph_count"] == 2

    def test_empty_document(self):
        """A document with no paragraphs returns empty text and count 0."""
        with _patch_document([]):
            result = extract_text(b"fake-docx-bytes")

        assert result["text"] == ""
        assert result["paragraph_count"] == 0

    def test_empty_paragraphs_excluded_from_text(self):
        """Empty paragraphs are counted but excluded from text output."""
        with _patch_document([
            _fake_paragraph("Content"),
            _fake_paragraph(""),
            _fake_paragraph("   "),
            _fake_paragraph("More content"),
        ]):
            result = extract_text(b"fake-docx-bytes")

        assert result["paragraph_count"] == 4
        # Only non-empty paragraphs appear in the text
        assert "Content" in result["text"]
        assert "More content" in result["text"]
        lines = result["text"].split("\n")
        assert len(lines) == 2

    def test_return_structure_keys(self):
        """Returned dict has exactly the expected keys."""
        with _patch_document([_fake_paragraph("text")]):
            result = extract_text(b"fake-docx-bytes")

        assert set(result.keys()) == {"text", "paragraph_count"}
