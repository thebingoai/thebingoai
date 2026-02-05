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
