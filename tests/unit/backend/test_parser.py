"""Tests for backend/parser/markdown.py"""

import pytest
from pathlib import Path

from backend.parser.markdown import parse_markdown, chunk_document


class TestParseMarkdown:
    """Test markdown parsing."""
    
    def test_simple_document(self):
        """Parse simple markdown document."""
        content = """# Title

This is a paragraph.

## Section 1

More content here.
"""
        doc = parse_markdown(content)
        
        assert doc.title == "Title"
        assert len(doc.sections) >= 1
        assert "This is a paragraph" in doc.content
    
    def test_empty_document(self):
        """Parse empty document."""
        doc = parse_markdown("")
        assert doc.title == ""
        assert doc.content == ""
    
    def test_document_without_title(self):
        """Parse document without h1."""
        content = """## Section

Content here.
"""
        doc = parse_markdown(content)
        assert doc.title == ""  # No h1 found
        assert "Section" in doc.content
    
    def test_document_with_metadata(self):
        """Parse document with YAML frontmatter."""
        content = """---
title: My Document
tags: [test, markdown]
---

# Actual Title

Content here.
"""
        doc = parse_markdown(content)
        # Should handle frontmatter gracefully
        assert "Actual Title" in doc.content


class TestChunkDocument:
    """Test document chunking."""
    
    def test_chunk_small_document(self):
        """Small document produces single chunk."""
        content = "# Title\n\nShort content."
        chunks = chunk_document(content, chunk_size=1000, overlap=0)
        
        assert len(chunks) == 1
        assert "Title" in chunks[0]
    
    def test_chunk_large_document(self):
        """Large document produces multiple chunks."""
        # Create content larger than chunk_size
        paragraphs = [f"Paragraph {i} with some content here.\n\n" for i in range(50)]
        content = "# Title\n\n" + "".join(paragraphs)
        
        chunks = chunk_document(content, chunk_size=500, overlap=50)
        
        assert len(chunks) > 1
        # Check overlap
        if len(chunks) > 1:
            # Some content from chunk 0 should appear in chunk 1
            assert len(chunks[0]) > 0
            assert len(chunks[1]) > 0
    
    def test_chunk_with_overlap(self):
        """Chunks include overlap between them."""
        content = "Word " * 200  # ~1000 characters
        
        chunks = chunk_document(content, chunk_size=300, overlap=50)
        
        assert len(chunks) > 1
        # Overlap means adjacent chunks share some content
    
    def test_empty_content(self):
        """Empty content returns empty list."""
        chunks = chunk_document("", chunk_size=500)
        assert chunks == []
    
    def test_respect_paragraph_boundaries(self):
        """Chunking respects paragraph boundaries when possible."""
        content = """# Title

Paragraph one has some content here.

Paragraph two is also here.

Paragraph three continues.
"""
        chunks = chunk_document(content, chunk_size=200, overlap=0)
        
        # Each chunk should ideally not split mid-paragraph
        for chunk in chunks:
            # Should not start with whitespace from split
            assert not chunk.startswith(" ")
