"""Tests for resolver/folder_resolver.py"""

import pytest
from pathlib import Path

from cli.resolver.folder_resolver import (
    extract_folder_references,
    remove_folder_references,
    resolve_folder,
    get_folder_file_count,
    suggest_folder_names
)


class TestExtractFolderReferences:
    """Test extracting @folder references from text."""
    
    def test_simple_reference(self):
        """Extract simple @folder reference."""
        text = "What's in @my-notes?"
        refs = extract_folder_references(text)
        assert refs == ["my-notes"]
    
    def test_reference_at_start(self):
        """Extract @folder at start of text."""
        text = "@docs explain this"
        refs = extract_folder_references(text)
        assert refs == ["docs"]
    
    def test_multiple_references(self):
        """Extract multiple @folder references."""
        text = "Check @notes and @docs for info"
        refs = extract_folder_references(text)
        assert refs == ["notes", "docs"]
    
    def test_no_reference(self):
        """No references in plain text."""
        text = "Just a regular question"
        refs = extract_folder_references(text)
        assert refs == []
    
    def test_empty_string(self):
        """Empty string returns empty list."""
        refs = extract_folder_references("")
        assert refs == []
    
    def test_reference_with_special_chars(self):
        """References with hyphens and underscores."""
        text = "Look at @my-notes_folder and @docs-v2"
        refs = extract_folder_references(text)
        assert refs == ["my-notes_folder", "docs-v2"]
    
    def test_reference_with_path(self):
        """References that look like paths."""
        text = "Check @./docs or @~/notes"
        refs = extract_folder_references(text)
        assert refs == ["./docs", "~/notes"]


class TestRemoveFolderReferences:
    """Test removing @folder references from text."""
    
    def test_remove_single_reference(self):
        """Remove single @folder reference."""
        text = "@my-notes what is this?"
        cleaned = remove_folder_references(text)
        assert cleaned == "what is this?"
    
    def test_remove_multiple_references(self):
        """Remove multiple @folder references."""
        text = "@notes check @docs for this"
        cleaned = remove_folder_references(text)
        # Note: may have extra whitespace from removal
        assert "check" in cleaned
        assert "for this" in cleaned
        assert "@notes" not in cleaned
        assert "@docs" not in cleaned
    
    def test_no_change_without_references(self):
        """Text without references unchanged."""
        text = "Just a question"
        cleaned = remove_folder_references(text)
        assert cleaned == "Just a question"
    
    def test_remove_with_path_reference(self):
        """Remove path-style references."""
        text = "@./docs explain this"
        cleaned = remove_folder_references(text)
        assert cleaned == "explain this"


class TestResolveFolder:
    """Test resolving @folder references to actual paths."""
    
    def test_resolve_relative_path(self, tmp_path, monkeypatch):
        """Resolve relative path from current directory."""
        # Create folder in tmp directory
        test_folder = tmp_path / "test-docs"
        test_folder.mkdir()
        
        # Change to tmp_path
        monkeypatch.chdir(tmp_path)
        
        result = resolve_folder("test-docs")
        assert result is not None
        path, name = result
        assert path == test_folder
        assert name == "test-docs"
    
    def test_resolve_nonexistent_folder(self, tmp_path, monkeypatch):
        """Return None for non-existent folder."""
        monkeypatch.chdir(tmp_path)
        
        result = resolve_folder("nonexistent")
        assert result is None
    
    def test_resolve_absolute_path(self, tmp_path):
        """Resolve absolute path reference."""
        test_folder = tmp_path / "my-docs"
        test_folder.mkdir()
        
        result = resolve_folder(str(test_folder))
        assert result is not None
        path, name = result
        assert path == test_folder
        assert name == "my-docs"


class TestGetFolderFileCount:
    """Test counting markdown files in folder."""
    
    def test_count_markdown_files(self, tmp_path):
        """Count .md files recursively."""
        # Create files
        (tmp_path / "doc1.md").write_text("# Doc 1")
        (tmp_path / "doc2.md").write_text("# Doc 2")
        (tmp_path / "not-md.txt").write_text("Not markdown")
        
        # Create subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "doc3.md").write_text("# Doc 3")
        
        count = get_folder_file_count(tmp_path)
        assert count == 3  # Only .md files
    
    def test_empty_folder(self, tmp_path):
        """Empty folder returns 0."""
        count = get_folder_file_count(tmp_path)
        assert count == 0
    
    def test_no_markdown_files(self, tmp_path):
        """Folder with no .md files returns 0."""
        (tmp_path / "file.txt").write_text("text")
        (tmp_path / "file.py").write_text("python")
        
        count = get_folder_file_count(tmp_path)
        assert count == 0


class TestSuggestFolderNames:
    """Test folder name suggestions."""
    
    def test_suggest_from_cache(self, empty_cache_dir, sample_markdown_folder):
        """Suggest indexed folder names."""
        from cli.cache.index_cache import update_cache
        
        # Add to cache
        update_cache(
            folder_name="my-notes",
            folder_path=sample_markdown_folder,
            namespace="my-notes",
            file_count=1,
            chunk_count=1,
            files={}
        )
        
        suggestions = suggest_folder_names("my")
        assert "my-notes" in suggestions
    
    def test_suggest_limit(self, empty_cache_dir, tmp_path, monkeypatch):
        """Suggestions limited to 10 items."""
        monkeypatch.chdir(tmp_path)
        
        # Create many folders
        for i in range(15):
            (tmp_path / f"folder{i}").mkdir()
        
        suggestions = suggest_folder_names("folder")
        assert len(suggestions) <= 10
    
    def test_no_matches(self, empty_cache_dir):
        """No suggestions when nothing matches."""
        suggestions = suggest_folder_names("xyz")
        assert suggestions == []
