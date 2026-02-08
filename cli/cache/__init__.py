"""Cache module for CLI."""
from cli.cache.index_cache import (
    is_folder_indexed,
    get_folder_info,
    update_cache,
    clear_cache,
    list_indexed_folders,
    get_file_hash,
    get_changed_files,
    get_removed_files,
)

__all__ = [
    "is_folder_indexed",
    "get_folder_info",
    "update_cache",
    "clear_cache",
    "list_indexed_folders",
    "get_file_hash",
    "get_changed_files",
    "get_removed_files",
]
