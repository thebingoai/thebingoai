"""Index cache system for tracking indexed folders."""

from pathlib import Path
from datetime import datetime
import hashlib
import json
from typing import Optional

CACHE_FILE = Path.home() / ".mdcli" / "index_cache.json"


def _ensure_cache_dir():
    """Ensure the cache directory exists."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


def get_file_hash(file_path: Path) -> str:
    """Get MD5 hash of file content."""
    return hashlib.md5(file_path.read_bytes()).hexdigest()


def _load_cache() -> dict:
    """Load the cache file or return empty structure."""
    _ensure_cache_dir()
    if not CACHE_FILE.exists():
        return {"indexes": {}}
    try:
        return json.loads(CACHE_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return {"indexes": {}}


def _save_cache(cache: dict):
    """Save the cache to disk."""
    _ensure_cache_dir()
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def is_folder_indexed(folder_name: str) -> bool:
    """Check if folder has been indexed."""
    cache = _load_cache()
    return folder_name in cache.get("indexes", {})


def get_folder_info(folder_name: str) -> Optional[dict]:
    """Get cached info about an indexed folder."""
    cache = _load_cache()
    return cache.get("indexes", {}).get(folder_name)


def get_changed_files(folder_name: str, folder_path: Path) -> list[Path]:
    """Compare current files with cache, return changed/new files."""
    cache = _load_cache()
    folder_cache = cache.get("indexes", {}).get(folder_name, {})
    cached_files = folder_cache.get("files", {})
    
    changed = []
    md_files = list(Path(folder_path).glob("**/*.md"))
    
    for file_path in md_files:
        rel_path = str(file_path.relative_to(folder_path))
        current_hash = get_file_hash(file_path)
        
        if rel_path not in cached_files or cached_files[rel_path] != current_hash:
            changed.append(file_path)
    
    return changed


def get_removed_files(folder_name: str, folder_path: Path) -> list[str]:
    """Get list of files that were removed from the folder."""
    cache = _load_cache()
    folder_cache = cache.get("indexes", {}).get(folder_name, {})
    cached_files = folder_cache.get("files", {})
    
    current_files = {str(f.relative_to(folder_path)) for f in Path(folder_path).glob("**/*.md")}
    removed = [f for f in cached_files if f not in current_files]
    
    return removed


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
        "files": files
    }
    
    _save_cache(cache)


def clear_cache(folder_name: str = None) -> None:
    """Clear cache for specific folder or all."""
    if folder_name:
        cache = _load_cache()
        if folder_name in cache.get("indexes", {}):
            del cache["indexes"][folder_name]
            _save_cache(cache)
    else:
        _ensure_cache_dir()
        _save_cache({"indexes": {}})


def list_indexed_folders() -> list[dict]:
    """List all indexed folders with their info."""
    cache = _load_cache()
    folders = []
    for name, info in cache.get("indexes", {}).items():
        folders.append({
            "name": name,
            **info
        })
    return folders


def get_folder_namespace(folder_name: str) -> Optional[str]:
    """Get the namespace for a folder."""
    info = get_folder_info(folder_name)
    return info.get("namespace") if info else None


def delete_folder_cache(folder_name: str) -> bool:
    """Delete a folder from cache. Returns True if deleted."""
    cache = _load_cache()
    if folder_name in cache.get("indexes", {}):
        del cache["indexes"][folder_name]
        _save_cache(cache)
        return True
    return False
