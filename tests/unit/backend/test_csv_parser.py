"""Tests for the CSV parser extract_text utility."""

import pytest

from backend.parser.csv_parser import extract_text


# ---------------------------------------------------------------------------
# Basic parsing
# ---------------------------------------------------------------------------

class TestCSVParserBasic:
    """Tests for basic CSV parsing behaviour."""

    def test_simple_csv(self):
        """A basic two-column CSV returns correct text, headers and row_count."""
        csv_bytes = b"name,age\nAlice,30\nBob,25\n"
        result = extract_text(csv_bytes)

        assert result["headers"] == ["name", "age"]
        assert result["row_count"] == 2
        assert "Alice" in result["text"]
        assert "Bob" in result["text"]

    def test_headers_extracted(self):
        """Headers are returned as a list regardless of data rows."""
        csv_bytes = b"col_a,col_b,col_c\n1,2,3\n"
        result = extract_text(csv_bytes)
        assert result["headers"] == ["col_a", "col_b", "col_c"]

    def test_empty_csv(self):
        """An empty CSV (no headers, no rows) produces empty results."""
        csv_bytes = b""
        result = extract_text(csv_bytes)

        assert result["headers"] == []
        assert result["row_count"] == 0
        assert result["text"] == ""

    def test_headers_only_no_data_rows(self):
        """A CSV with headers but no data rows returns row_count 0."""
        csv_bytes = b"x,y,z\n"
        result = extract_text(csv_bytes)

        assert result["headers"] == ["x", "y", "z"]
        assert result["row_count"] == 0


# ---------------------------------------------------------------------------
# Text formatting
# ---------------------------------------------------------------------------

class TestCSVParserTextFormat:
    """Verify the human-readable text output format."""

    def test_text_contains_pipe_delimiters(self):
        """Formatted text uses pipe delimiters between columns."""
        csv_bytes = b"a,b\n1,2\n"
        result = extract_text(csv_bytes)

        lines = result["text"].split("\n")
        # Header line
        assert " | " in lines[0]
        # Separator line
        assert lines[1].startswith("-")
        # Data line
        assert " | " in lines[2]

    def test_return_structure_keys(self):
        """Returned dict has exactly the expected keys."""
        csv_bytes = b"h1,h2\nv1,v2\n"
        result = extract_text(csv_bytes)

        assert set(result.keys()) == {"text", "headers", "row_count"}
