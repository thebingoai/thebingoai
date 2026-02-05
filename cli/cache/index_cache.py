import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional
import os

CACHE_DIR = Path.home() / ".mdcli"
CACHE_FILE = CACHE_DIR / "index_cache.json"

def _ensure_cache_dir():
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _load_cache() -> dict:
    """Load cache from disk."""
    _ensure_cache_dir()
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            return {"indexes": {}}
    return {"indexes": {}}

def _save_cache(cache: dict) -> None:
    """Save cache to disk."""
    _ensure_cache_dir()
    CACHE_FILE.write_text(json.dumps(cache, indent=2, default=str))

def get_file_hash(file_path: Path) -> str:
    """Get MD5 hash of file content."""
    return hashlib.md5(file_path.read_bytes()).hexdigest()

def is_folder_indexed(folder_name: str) -> bool:
    """Check if folder has been indexed."""
    cache = _load_cache()
    return folder_name in cache.get("indexes", {})

def get_folder_info(folder_name: str) -> Optional[dict]:
    """Get cached info about an indexed folder."""
    cache = _load_cache()
    return cache.get("indexes", {}).get(folder_name)

def get_folder_path(folder_name: str) -> Optional[Path]:
    """Get the path for an indexed folder."""
    info = get_folder_info(folder_name)
    if info and "path" in info:
        return Path(info["path"])
    return None

def get_namespace(folder_name: str) -> Optional[str]:
    """Get the namespace for an indexed folder."""
    info = get_folder_info(folder_name)
    if info:
        return info.get("namespace")
    return None

def get_changed_files(folder_name: str, folder_path: Path) -> tuple[list[Path], list[Path], list[str]]:
    """
    Compare current files with cache.

    Returns:
        (new_files, modified_files, deleted_file_names)
    """
    info = get_folder_info(folder_name)
    if not info:
        # Not indexed - all files are new
        md_files = list(folder_path.glob("**/*.md"))
        return md_files, [], []

    cached_files = info.get("files", {})
    current_files = {}

    for f in folder_path.glob("**/*.md"):
        rel_path = str(f.relative_to(folder_path))
        current_files[rel_path] = get_file_hash(f)

    new_files = []
    modified_files = []
    deleted_files = []

    # Find new and modified
    for rel_path, current_hash in current_files.items():
        full_path = folder_path / rel_path
        if rel_path not in cached_files:
            new_files.append(full_path)
        elif cached_files[rel_path].get("hash") != current_hash:
            modified_files.append(full_path)

    # Find deleted
    for rel_path in cached_files:
        if rel_path not in current_files:
            deleted_files.append(rel_path)

    return new_files, modified_files, deleted_files

def update_cache(
    folder_name: str,
    folder_path: Path,
    namespace: str,
    file_count: int,
    chunk_count: int,
    files: dict[str, str]  # filename -> hash
) -> None:
    """Update cache after successful indexing."""
    cache = _load_cache()

    cache["indexes"][folder_name] = {
        "path": str(folder_path.resolve()),
        "namespace": namespace,
        "indexed_at": datetime.utcnow().isoformat(),
        "file_count": file_count,
        "chunk_count": chunk_count,
        "files": {
            name: {"hash": hash_val, "indexed_at": datetime.utcnow().isoformat()}
            for name, hash_val in files.items()
        }
    }

    _save_cache(cache)

def clear_cache(folder_name: Optional[str] = None) -> None:
    """Clear cache for specific folder or all."""
    if folder_name:
        cache = _load_cache()
        if folder_name in cache.get("indexes", {}):
            del cache["indexes"][folder_name]
            _save_cache(cache)
    else:
        _save_cache({"indexes": {}})

def list_indexed_folders() -> list[dict]:
    """List all indexed folders with their info."""
    cache = _load_cache()
    result = []
    for name, info in cache.get("indexes", {}).items():
        result.append({
            "name": name,
            "path": info.get("path"),
            "namespace": info.get("namespace"),
            "indexed_at": info.get("indexed_at"),
            "file_count": info.get("file_count", 0)
        })
    return result
