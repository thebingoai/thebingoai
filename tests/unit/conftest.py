"""Test configuration and fixtures for Bingo."""

import pytest
import tempfile
from pathlib import Path
from typing import Generator


@pytest.fixture
def sample_markdown_file() -> Generator[Path, None, None]:
    """Create a sample markdown file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("""# Test Document

This is a test document for the bingo project.

## Features

- Markdown indexing
- Vector search
- RAG chat

## Testing

This document helps verify the upload functionality works correctly.
""")
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def sample_markdown_folder() -> Generator[Path, None, None]:
    """Create a folder with multiple markdown files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        
        # Create multiple markdown files
        (folder / "doc1.md").write_text("""# Document 1
This is the first test document.
It has multiple lines of content.
""")
        
        (folder / "doc2.md").write_text("""# Document 2
This is the second test document.
More content here for testing.
""")
        
        # Create subdirectory
        subdir = folder / "subdir"
        subdir.mkdir()
        (subdir / "doc3.md").write_text("""# Document 3
Nested document in subdirectory.
""")
        
        yield folder
