"""Tests for cache/index_cache.py"""

import json
from pathlib import Path
from datetime import datetime

import pytest

from cli.cache.index_cache import (
    is_folder_indexed,
    get_folder_info,
    update_cache,
    clear_cache,
    list_indexed_folders,
    get_file_hash,
    get_changed_files,
    delete_folder_cache,
    _load_cache,
    _save_cache
)


class TestCacheBasics:
    """Test basic cache operations."""
    
    def test_cache_file_created(self, empty_cache_dir):
        """Cache file should be created on first access."""
        cache = _load_cache()
        assert "indexes" in cache
        assert cache["indexes"] == {}
    
    def test_update_cache(self, empty_cache_dir, sample_markdown_folder):
        """Test updating cache with folder info."""
        folder = sample_markdown_folder
        
        update_cache(
            folder_name="test-folder",
            folder_path=folder,
            namespace="test-namespace",
            file_count=3,
            chunk_count=10,
            files={"doc1.md": "hash1", "doc2.md": "hash2"}
        )
        
        # Verify cache was updated
        assert is_folder_indexed("test-folder")
        info = get_folder_info("test-folder")
        assert info["namespace"] == "test-namespace"
        assert info["file_count"] == 3
        assert info["chunk_count"] == 10
    
    def test_get_folder_info_not_found(self, empty_cache_dir):
        """Getting info for non-existent folder returns None."""
        result = get_folder_info("non-existent")
        assert result is None
    
    def test_is_folder_indexed(self, empty_cache_dir, sample_markdown_folder):
        """Test checking if folder is indexed."""
        # Initially not indexed
        assert not is_folder_indexed("test-folder")
        
        # After adding to cache
        update_cache(
            folder_name="test-folder",
            folder_path=sample_markdown_folder,
            namespace="test",
            file_count=1,
            chunk_count=1,
            files={}
        )
        
        assert is_folder_indexed("test-folder")


class TestFileHashing:
    """Test file hash operations."""
    
    def test_get_file_hash(self, sample_markdown_file):
        """Test that file hash is consistent."""
        hash1 = get_file_hash(sample_markdown_file)
        hash2 = get_file_hash(sample_markdown_file)
        
        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 hash length
    
    def test_get_file_hash_different_files(self, sample_markdown_folder):
        """Different files should have different hashes."""
        folder = sample_markdown_folder
        
        hash1 = get_file_hash(folder / "doc1.md")
        hash2 = get_file_hash(folder / "doc2.md")
        
        assert hash1 != hash2


class TestChangedFiles:
    """Test detecting changed files."""
    
    def test_no_changes(self, empty_cache_dir, sample_markdown_folder):
        """No changes when files match cache."""
        folder = sample_markdown_folder
        
        # Calculate current hashes
        files = {
            "doc1.md": get_file_hash(folder / "doc1.md"),
            "doc2.md": get_file_hash(folder / "doc2.md"),
            "subdir/doc3.md": get_file_hash(folder / "subdir" / "doc3.md"),
        }
        
        # Update cache
        update_cache(
            folder_name="test-folder",
            folder_path=folder,
            namespace="test",
            file_count=3,
            chunk_count=10,
            files=files
        )
        
        # Should be no changes
        changed = get_changed_files("test-folder", folder)
        assert len(changed) == 0
    
    def test_detect_changed_file(self, empty_cache_dir, sample_markdown_folder):
        """Detect when a file has been modified."""
        folder = sample_markdown_folder
        
        # Add to cache with wrong hash
        update_cache(
            folder_name="test-folder",
            folder_path=folder,
            namespace="test",
            file_count=1,
            chunk_count=1,
            files={"doc1.md": "wrong-hash"}
        )
        
        # Should detect doc1.md as changed
        changed = get_changed_files("test-folder", folder)
        assert len(changed) >= 1
        assert any("doc1.md" in str(f) for f in changed)


class TestCacheManagement:
    """Test cache management operations."""
    
    def test_list_indexed_folders(self, empty_cache_dir, sample_markdown_folder):
        """Test listing all indexed folders."""
        # Initially empty
        folders = list_indexed_folders()
        assert len(folders) == 0
        
        # Add folders
        update_cache(
            folder_name="folder1",
            folder_path=sample_markdown_folder,
            namespace="ns1",
            file_count=1,
            chunk_count=1,
            files={}
        )
        update_cache(
            folder_name="folder2",
            folder_path=sample_markdown_folder,
            namespace="ns2",
            file_count=1,
            chunk_count=1,
            files={}
        )
        
        folders = list_indexed_folders()
        assert len(folders) == 2
        names = {f["name"] for f in folders}
        assert names == {"folder1", "folder2"}
    
    def test_delete_folder_cache(self, empty_cache_dir, sample_markdown_folder):
        """Test deleting a folder from cache."""
        update_cache(
            folder_name="test-folder",
            folder_path=sample_markdown_folder,
            namespace="test",
            file_count=1,
            chunk_count=1,
            files={}
        )
        
        assert is_folder_indexed("test-folder")
        
        # Delete
        result = delete_folder_cache("test-folder")
        assert result is True
        assert not is_folder_indexed("test-folder")
    
    def test_delete_folder_cache_not_found(self, empty_cache_dir):
        """Deleting non-existent folder returns False."""
        result = delete_folder_cache("non-existent")
        assert result is False
    
    def test_clear_cache(self, empty_cache_dir, sample_markdown_folder):
        """Test clearing entire cache."""
        # Add some folders
        update_cache(
            folder_name="folder1",
            folder_path=sample_markdown_folder,
            namespace="ns1",
            file_count=1,
            chunk_count=1,
            files={}
        )
        
        # Clear all
        clear_cache()
        
        # Should be empty
        folders = list_indexed_folders()
        assert len(folders) == 0
        assert not is_folder_indexed("folder1")
    
    def test_clear_cache_specific(self, empty_cache_dir, sample_markdown_folder):
        """Test clearing specific folder only."""
        update_cache(
            folder_name="folder1",
            folder_path=sample_markdown_folder,
            namespace="ns1",
            file_count=1,
            chunk_count=1,
            files={}
        )
        update_cache(
            folder_name="folder2",
            folder_path=sample_markdown_folder,
            namespace="ns2",
            file_count=1,
            chunk_count=1,
            files={}
        )
        
        # Clear only folder1
        clear_cache("folder1")
        
        assert not is_folder_indexed("folder1")
        assert is_folder_indexed("folder2")
