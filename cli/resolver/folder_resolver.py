"""Folder resolution for @folder references."""

import re
from pathlib import Path
from typing import Optional


def resolve_folder(reference: str) -> Optional[tuple[Path, str]]:
    """
    Resolve @folder reference to actual path.

    Resolution order:
        1. Cached folder name (from index cache)
        2. Relative path from current working directory
        3. Absolute path
        4. Common locations search (Documents, Desktop, Projects, etc.)

    Args:
        reference: Folder reference (e.g., "my-notes", "./docs", "~/Documents/notes")

    Returns:
        (folder_path, folder_name) tuple if found, None otherwise
    """
    from cli.cache.index_cache import get_folder_info

    # Clean up reference - remove leading @ and whitespace
    reference = reference.strip().lstrip("@")

    # 1. Check if it's a cached folder name
    cached = get_folder_info(reference)
    if cached:
        return Path(cached["path"]), reference

    # 2. Check if it's a path (relative or absolute)
    path = Path(reference).expanduser()

    if not path.is_absolute():
        # Relative path from current directory
        path = Path.cwd() / path

    if path.exists() and path.is_dir():
        return path, path.name

    # 3. Search common locations
    common_locations = [
        Path.home() / "Documents",
        Path.home() / "Desktop",
        Path.home() / "Projects",
        Path.home() / "Workspace",
        Path.home(),
    ]

    for location in common_locations:
        candidate = location / reference
        if candidate.exists() and candidate.is_dir():
            return candidate, reference

    return None


def extract_folder_references(text: str) -> list[str]:
    """
    Extract @folder references from user input.

    Examples:
        "What's in @my-notes?" -> ["my-notes"]
        "@docs explain this" -> ["docs"]
        '@"folder with spaces" help' -> ["folder with spaces"]
        "no reference here" -> []

    Args:
        text: User input text

    Returns:
        List of folder references (without @ symbol)
    """
    # Pattern matches:
    # - @word-chars (simple names)
    # - @"quoted with spaces"
    # - @path/to/folder
    pattern = r'@([a-zA-Z0-9_./~-]+|"[^"]+")'
    matches = re.findall(pattern, text)
    return [m.strip('"') for m in matches]


def remove_folder_references(text: str) -> str:
    """
    Remove @folder references from text, leaving the question.

    Args:
        text: User input text with @folder references

    Returns:
        Cleaned text without folder references
    """
    # Remove @folder patterns and clean up extra whitespace
    cleaned = re.sub(r'@([a-zA-Z0-9_./~-]+|"[^"]+")\s*', ' ', text)
    return cleaned.strip()


def get_folder_file_count(folder_path: Path) -> int:
    """
    Count markdown files in a folder recursively.

    Args:
        folder_path: Path to the folder

    Returns:
        Number of .md files found
    """
    return len(list(folder_path.glob("**/*.md")))


def suggest_folder_names(partial: str) -> list[str]:
    """
    Suggest folder names based on partial input for autocomplete.

    Searches both indexed folders and current directory.

    Args:
        partial: Partial folder name input

    Returns:
        List of up to 10 matching folder names
    """
    from cli.cache.index_cache import list_indexed_folders

    suggestions: list[str] = []

    # Check indexed folders
    for folder in list_indexed_folders():
        name = folder["name"]
        if partial.lower() in name.lower():
            suggestions.append(name)

    # Also check current directory
    for item in Path.cwd().iterdir():
        if item.is_dir() and partial.lower() in item.name.lower():
            if item.name not in suggestions:
                suggestions.append(item.name)

    return suggestions[:10]  # Limit to 10 suggestions
