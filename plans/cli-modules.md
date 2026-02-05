# CLI Modules

Complete implementations for CLI components: API client, configuration, index cache, and folder resolver.

---

## 1. Backend API Client (for CLI)

### Create `cli/api/__init__.py`

```python
# Empty file - package marker
```

### Create `cli/api/client.py`

```python
import httpx
from typing import Optional, AsyncGenerator
from pathlib import Path
from cli.config import get_config

class APIError(Exception):
    """API error with status code and message."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API Error {status_code}: {message}")

class BackendClient:
    """HTTP client for backend API."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 120.0):
        config = get_config()
        self.base_url = base_url or config.backend_url
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    def _handle_error(self, response: httpx.Response) -> None:
        """Raise APIError for non-2xx responses."""
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise APIError(response.status_code, detail)

    # Health
    async def health(self) -> dict:
        """Check backend health."""
        response = await self._client.get("/health")
        self._handle_error(response)
        return response.json()

    async def health_detailed(self) -> dict:
        """Get detailed health status."""
        response = await self._client.get("/health/detailed")
        self._handle_error(response)
        return response.json()

    # Upload
    async def upload_file(
        self,
        file_path: Path,
        namespace: str = "default",
        tags: list[str] = None,
        webhook_url: Optional[str] = None,
        force_async: bool = False
    ) -> dict:
        """Upload a markdown file."""
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "text/markdown")}
            data = {
                "namespace": namespace,
                "tags": ",".join(tags or []),
                "force_async": str(force_async).lower()
            }
            if webhook_url:
                data["webhook_url"] = webhook_url

            response = await self._client.post(
                "/api/upload",
                files=files,
                data=data
            )
        self._handle_error(response)
        return response.json()

    # Query
    async def query(
        self,
        query: str,
        namespace: str = "default",
        top_k: int = 5,
        filter: Optional[dict] = None
    ) -> dict:
        """Vector similarity search."""
        payload = {
            "query": query,
            "namespace": namespace,
            "top_k": top_k
        }
        if filter:
            payload["filter"] = filter

        response = await self._client.post("/api/query", json=payload)
        self._handle_error(response)
        return response.json()

    async def search(
        self,
        q: str,
        namespace: str = "default",
        limit: int = 5
    ) -> dict:
        """Simple search via query params."""
        response = await self._client.get(
            "/api/search",
            params={"q": q, "namespace": namespace, "limit": limit}
        )
        self._handle_error(response)
        return response.json()

    # Ask (RAG)
    async def ask(
        self,
        question: str,
        namespace: str = "default",
        top_k: int = 5,
        provider: str = "openai",
        model: Optional[str] = None,
        temperature: float = 0.7,
        thread_id: Optional[str] = None
    ) -> dict:
        """Ask with RAG (non-streaming)."""
        payload = {
            "question": question,
            "namespace": namespace,
            "top_k": top_k,
            "provider": provider,
            "temperature": temperature,
            "stream": False
        }
        if model:
            payload["model"] = model
        if thread_id:
            payload["thread_id"] = thread_id

        response = await self._client.post("/api/ask", json=payload)
        self._handle_error(response)
        return response.json()

    async def ask_stream(
        self,
        question: str,
        namespace: str = "default",
        top_k: int = 5,
        provider: str = "openai",
        model: Optional[str] = None,
        temperature: float = 0.7,
        thread_id: Optional[str] = None
    ) -> AsyncGenerator[dict, None]:
        """Ask with RAG (streaming)."""
        import json

        payload = {
            "question": question,
            "namespace": namespace,
            "top_k": top_k,
            "provider": provider,
            "temperature": temperature,
            "stream": True
        }
        if model:
            payload["model"] = model
        if thread_id:
            payload["thread_id"] = thread_id

        async with self._client.stream("POST", "/api/ask", json=payload) as response:
            self._handle_error(response)
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        continue

    # Providers
    async def get_providers(self) -> dict:
        """List available LLM providers."""
        response = await self._client.get("/api/providers")
        self._handle_error(response)
        return response.json()

    # Status
    async def get_status(self) -> dict:
        """Get index status."""
        response = await self._client.get("/api/status")
        self._handle_error(response)
        return response.json()

    # Jobs
    async def get_job(self, job_id: str) -> dict:
        """Get job status."""
        response = await self._client.get(f"/api/jobs/{job_id}")
        self._handle_error(response)
        return response.json()

    async def list_jobs(
        self,
        namespace: Optional[str] = None,
        limit: int = 50
    ) -> dict:
        """List recent jobs."""
        params = {"limit": limit}
        if namespace:
            params["namespace"] = namespace
        response = await self._client.get("/api/jobs", params=params)
        self._handle_error(response)
        return response.json()

    # Conversation
    async def get_conversation(self, thread_id: str) -> dict:
        """Get conversation history."""
        response = await self._client.get(f"/api/conversation/{thread_id}")
        self._handle_error(response)
        return response.json()

    async def delete_conversation(self, thread_id: str) -> dict:
        """Clear conversation history."""
        response = await self._client.delete(f"/api/conversation/{thread_id}")
        self._handle_error(response)
        return response.json()


# Convenience function for sync contexts
def get_client() -> BackendClient:
    """Get a new BackendClient instance."""
    return BackendClient()
```

---

## 2. CLI Configuration

### Create `cli/config.py`

```python
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

CONFIG_DIR = Path.home() / ".mdcli"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

@dataclass
class Config:
    backend_url: str = "http://localhost:8000"
    webhook_url: Optional[str] = None
    default_provider: str = "openai"
    default_namespace: str = "default"

def _ensure_config_dir():
    """Ensure config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def get_config() -> Config:
    """Load configuration from file."""
    _ensure_config_dir()

    if CONFIG_FILE.exists():
        try:
            data = yaml.safe_load(CONFIG_FILE.read_text()) or {}
            return Config(
                backend_url=data.get("backend_url", "http://localhost:8000"),
                webhook_url=data.get("webhook_url"),
                default_provider=data.get("default_provider", "openai"),
                default_namespace=data.get("default_namespace", "default")
            )
        except Exception:
            pass

    return Config()

def save_config(config: Config) -> None:
    """Save configuration to file."""
    _ensure_config_dir()

    data = {
        "backend_url": config.backend_url,
        "default_provider": config.default_provider,
        "default_namespace": config.default_namespace
    }
    if config.webhook_url:
        data["webhook_url"] = config.webhook_url

    CONFIG_FILE.write_text(yaml.dump(data, default_flow_style=False))

def set_config_value(key: str, value: str) -> None:
    """Set a single config value."""
    config = get_config()

    if key == "backend_url":
        config.backend_url = value
    elif key == "webhook_url":
        config.webhook_url = value
    elif key == "default_provider":
        config.default_provider = value
    elif key == "default_namespace":
        config.default_namespace = value
    else:
        raise ValueError(f"Unknown config key: {key}")

    save_config(config)
```

---

## 3. Index Cache

Tracks which folders are indexed and their file hashes for change detection.

### Create `cli/cache/__init__.py`

```python
# Empty file - package marker
```

### Create `cli/cache/index_cache.py`

```python
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
```

---

## 4. Folder Resolver

Resolves @folder references to actual paths.

### Create `cli/resolver/__init__.py`

```python
# Empty file - package marker
```

### Create `cli/resolver/folder_resolver.py`

```python
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
```

---

## Related Files

- [models.md](./models.md) - Pydantic models used by API client
- [backend-api.md](./backend-api.md) - Backend endpoints the client calls
- [phase-2.5-interactive-chat.md](./phase-2.5-interactive-chat.md) - TUI uses these modules
