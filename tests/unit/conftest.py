"""Test configuration and fixtures for LLM-MD-CLI."""

import pytest
import tempfile
from pathlib import Path
from typing import Generator


@pytest.fixture
def sample_markdown_file() -> Generator[Path, None, None]:
    """Create a sample markdown file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("""# Test Document

This is a test document for the llm-md-cli project.

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


@pytest.fixture
def mock_backend_url() -> str:
    """Return mock backend URL for testing."""
    return "http://localhost:8000"


@pytest.fixture
def empty_cache_dir(monkeypatch, tmp_path) -> Path:
    """Create temporary cache directory and patch CACHE_FILE."""
    cache_dir = tmp_path / ".mdcli"
    cache_dir.mkdir()
    cache_file = cache_dir / "index_cache.json"
    
    import cli.cache.index_cache as index_cache
    original_cache_file = index_cache.CACHE_FILE
    
    monkeypatch.setattr(index_cache, "CACHE_FILE", cache_file)
    
    yield cache_dir
    
    # Restore original
    monkeypatch.setattr(index_cache, "CACHE_FILE", original_cache_file)
