"""Folder resolution for @folder references."""

import re
from pathlib import Path
from typing import Optional, Tuple


def resolve_folder(reference: str) -> Optional[Tuple[Path, str]]:
    """
    Resolve @folder reference to actual path.

    Args:
        reference: Folder reference (e.g., "my-notes", "./docs", "~/Documents/notes")

    Returns:
        (folder_path, folder_name) or None if not found

    Resolution order:
        1. Cached folder name
        2. Relative path from cwd
        3. Absolute path
        4. Common locations search
    """
    from cli.cache.index_cache import get_folder_info
    
    # Clean up reference
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
        # Use the directory name as folder name
        folder_name = path.name
        return path, folder_name
    
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
    """
    # Pattern matches:
    # - @word-chars (simple names)
    # - @"quoted with spaces"
    # - @path/to/folder
    pattern = r'@([a-zA-Z0-9_./~-]+|"[^"]+")'
    matches = re.findall(pattern, text)
    return [m.strip('"') for m in matches]


def remove_folder_references(text: str) -> str:
    """Remove @folder references from text, leaving the question."""
    # Remove @folder patterns and clean up extra whitespace
    cleaned = re.sub(r'@([a-zA-Z0-9_./~-]+|"[^"]+")\s*', ' ', text)
    return cleaned.strip()


def get_folder_file_count(folder_path: Path) -> int:
    """Count markdown files in a folder (recursively)."""
    return len(list(folder_path.glob("**/*.md")))


def suggest_folder_names(partial: str) -> list[str]:
    """Suggest folder names based on partial input (for autocomplete)."""
    from cli.cache.index_cache import list_indexed_folders
    
    all_folders = list_indexed_folders()
    suggestions = []
    
    for folder in all_folders:
        name = folder["name"]
        if partial.lower() in name.lower():
            suggestions.append(name)
    
    # Also check current directory
    for item in Path.cwd().iterdir():
        if item.is_dir() and partial.lower() in item.name.lower():
            if item.name not in suggestions:
                suggestions.append(item.name)
    
    return suggestions[:10]  # Limit suggestions
