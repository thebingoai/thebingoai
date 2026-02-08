"""Folder resolver module for CLI."""
from cli.resolver.folder_resolver import (
    resolve_folder,
    extract_folder_references,
    remove_folder_references,
    get_folder_file_count,
    suggest_folder_names,
)

__all__ = [
    "resolve_folder",
    "extract_folder_references",
    "remove_folder_references",
    "get_folder_file_count",
    "suggest_folder_names",
]
