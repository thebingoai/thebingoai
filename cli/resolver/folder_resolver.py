import re
from pathlib import Path
from typing import Optional
from cli.cache.index_cache import get_folder_path, list_indexed_folders

# Common locations to search
SEARCH_PATHS = [
    Path.home() / "Documents",
    Path.home() / "Desktop",
    Path.home() / "Downloads",
    Path.home() / "Projects",
    Path.home(),
]

def resolve_folder(reference: str) -> Optional[tuple[Path, str]]:
    """
    Resolve @folder reference to actual path.

    Args:
        reference: Folder reference (e.g., "my-notes", "./docs", "~/Documents/notes")

    Returns:
        (folder_path, folder_name) or None if not found

    Resolution order:
        1. Cached folder name
        2. Relative path from cwd
        3. Absolute path / home expansion
        4. Common locations search
    """
    # Clean the reference
    reference = reference.strip().strip('"').strip("'")

    # 1. Check if it's a cached folder name
    cached_path = get_folder_path(reference)
    if cached_path and cached_path.exists():
        return cached_path, reference

    # 2. Try as relative path from cwd
    rel_path = Path.cwd() / reference
    if rel_path.exists() and rel_path.is_dir():
        return rel_path, rel_path.name

    # 3. Try as absolute path or with home expansion
    expanded = Path(reference).expanduser()
    if expanded.is_absolute() and expanded.exists() and expanded.is_dir():
        return expanded, expanded.name

    # 4. Search common locations
    for search_path in SEARCH_PATHS:
        candidate = search_path / reference
        if candidate.exists() and candidate.is_dir():
            return candidate, reference

    # 5. Fuzzy search in common locations (case-insensitive)
    reference_lower = reference.lower()
    for search_path in SEARCH_PATHS:
        if search_path.exists():
            for item in search_path.iterdir():
                if item.is_dir() and item.name.lower() == reference_lower:
                    return item, item.name

    return None

def extract_folder_references(text: str) -> list[str]:
    """
    Extract @folder references from user input.

    Handles:
        @my-notes
        @"folder with spaces"
        @./relative/path
        @~/home/path

    Returns:
        List of folder references (without @)
    """
    # Match @word, @"quoted string", or @path/like/this
    pattern = r'@(?:"([^"]+)"|([a-zA-Z0-9_\-./~]+))'
    matches = re.findall(pattern, text)

    results = []
    for quoted, unquoted in matches:
        ref = quoted if quoted else unquoted
        if ref:
            results.append(ref)

    return results

def remove_folder_references(text: str) -> str:
    """Remove @folder references from text, leaving the question."""
    # Remove @word, @"quoted", @path references
    pattern = r'@(?:"[^"]+"|[a-zA-Z0-9_\-./~]+)\s*'
    return re.sub(pattern, '', text).strip()

def suggest_folders(partial: str) -> list[str]:
    """
    Suggest folder names for autocomplete.

    Args:
        partial: Partial folder name typed by user

    Returns:
        List of matching folder names
    """
    suggestions = []
    partial_lower = partial.lower()

    # First, check indexed folders
    for folder in list_indexed_folders():
        if folder["name"].lower().startswith(partial_lower):
            suggestions.append(folder["name"])

    # Then check common locations
    for search_path in SEARCH_PATHS:
        if search_path.exists():
            for item in search_path.iterdir():
                if item.is_dir() and item.name.lower().startswith(partial_lower):
                    if item.name not in suggestions:
                        suggestions.append(item.name)

    return sorted(suggestions)[:10]  # Limit suggestions
