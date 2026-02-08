"""HTTP client for backend API with proper async context management."""

import httpx
from typing import Optional, AsyncGenerator
from pathlib import Path
from cli.config import get_config


class APIError(Exception):
    """
    API error with status code and message.

    Attributes:
        status_code: HTTP status code
        message: Error message from API or derived from status
    """

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"API Error {status_code}: {message}")


class BackendClient:
    """
    Async HTTP client for backend API.

    Usage:
        async with BackendClient() as client:
            result = await client.query("search term")

    Or with get_client() helper:
        async with get_client() as client:
            result = await client.query("search term")
    """

    def __init__(self, base_url: Optional[str] = None, timeout: float = 120.0) -> None:
        """
        Initialize the client.

        Args:
            base_url: Backend API URL (defaults to config)
            timeout: Request timeout in seconds
        """
        config = get_config()
        self.base_url: str = base_url or config.backend_url
        self.timeout: float = timeout
        self._client: Optional[httpx.AsyncClient] = None

    def _ensure_client(self) -> httpx.AsyncClient:
        """
        Ensure client is initialized.

        Returns:
            The HTTP client instance

        Raises:
            RuntimeError: If client not initialized via context manager
        """
        if self._client is None:
            raise RuntimeError(
                "BackendClient must be used as a context manager. "
                "Use 'async with BackendClient() as client:' or 'async with get_client() as client:'"
            )
        return self._client

    async def __aenter__(self) -> "BackendClient":
        """Initialize HTTP client when entering context."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout
        )
        return self

    async def __aexit__(self, *args) -> None:
        """Close HTTP client when exiting context."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _handle_error(self, response: httpx.Response) -> None:
        """
        Raise APIError for non-2xx responses.

        Args:
            response: HTTP response to check

        Raises:
            APIError: If response status code >= 400
        """
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise APIError(response.status_code, detail)

    # Health endpoints

    async def health(self) -> dict:
        """
        Check backend health.

        Returns:
            Health status dict with 'status' key
        """
        client = self._ensure_client()
        response = await client.get("/health")
        self._handle_error(response)
        return response.json()

    async def health_detailed(self) -> dict:
        """
        Get detailed health status.

        Returns:
            Detailed health dict with 'status' and 'checks' keys
        """
        client = self._ensure_client()
        response = await client.get("/health/detailed")
        self._handle_error(response)
        return response.json()

    # Upload endpoints

    async def upload_file(
        self,
        file_path: Path,
        namespace: str = "default",
        tags: list[str] | None = None,
        webhook_url: Optional[str] = None,
        force_async: bool = False
    ) -> dict:
        """
        Upload a markdown file to the backend.

        Args:
            file_path: Path to markdown file
            namespace: Namespace for the file
            tags: Optional tags for the file
            webhook_url: Optional webhook for completion notification
            force_async: Force async processing

        Returns:
            Upload response dict with status, chunks_created, etc.
        """
        client = self._ensure_client()

        # Open file outside the request for proper cleanup
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "text/markdown")}
            data = {
                "namespace": namespace,
                "tags": ",".join(tags or []),
                "force_async": str(force_async).lower()
            }
            if webhook_url:
                data["webhook_url"] = webhook_url

            response = await client.post("/api/upload", files=files, data=data)

        self._handle_error(response)
        return response.json()

    # Query endpoints

    async def query(
        self,
        query: str,
        namespace: str = "default",
        top_k: int = 5,
        filter: Optional[dict] = None
    ) -> dict:
        """
        Perform vector similarity search.

        Args:
            query: Search query text
            namespace: Namespace to search
            top_k: Number of results to return
            filter: Optional metadata filter

        Returns:
            Query response with results list
        """
        client = self._ensure_client()

        payload = {
            "query": query,
            "namespace": namespace,
            "top_k": top_k
        }
        if filter:
            payload["filter"] = filter

        response = await client.post("/api/query", json=payload)
        self._handle_error(response)
        return response.json()

    async def search(
        self,
        q: str,
        namespace: str = "default",
        limit: int = 5
    ) -> dict:
        """
        Simple search via query parameters.

        Args:
            q: Search query
            namespace: Namespace to search
            limit: Max results

        Returns:
            Search response dict
        """
        client = self._ensure_client()
        response = await client.get(
            "/api/search",
            params={"q": q, "namespace": namespace, "limit": limit}
        )
        self._handle_error(response)
        return response.json()

    # Chat/RAG endpoints

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
        """
        Ask a question with RAG (non-streaming).

        Args:
            question: User's question
            namespace: Namespace to search
            top_k: Context chunks to retrieve
            provider: LLM provider name
            model: Optional model override
            temperature: Generation temperature
            thread_id: Conversation thread ID

        Returns:
            Answer dict with answer, sources, thread_id
        """
        client = self._ensure_client()

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

        response = await client.post("/api/ask", json=payload)
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
        """
        Ask a question with RAG (streaming).

        Args:
            question: User's question
            namespace: Namespace to search
            top_k: Context chunks to retrieve
            provider: LLM provider name
            model: Optional model override
            temperature: Generation temperature
            thread_id: Conversation thread ID

        Yields:
            Stream event dicts with 'token', 'sources', or 'thread_id' keys
        """
        import json

        client = self._ensure_client()

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

        async with client.stream("POST", "/api/ask", json=payload) as response:
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

    # Provider endpoints

    async def get_providers(self) -> dict:
        """
        List available LLM providers.

        Returns:
            Providers dict with available providers and models
        """
        client = self._ensure_client()
        response = await client.get("/api/providers")
        self._handle_error(response)
        return response.json()

    # Status endpoints

    async def get_status(self) -> dict:
        """
        Get index status.

        Returns:
            Status dict with index statistics
        """
        client = self._ensure_client()
        response = await client.get("/api/status")
        self._handle_error(response)
        return response.json()

    # Job endpoints

    async def get_job(self, job_id: str) -> dict:
        """
        Get job status.

        Args:
            job_id: Job identifier

        Returns:
            Job info dict
        """
        client = self._ensure_client()
        response = await client.get(f"/api/jobs/{job_id}")
        self._handle_error(response)
        return response.json()

    async def list_jobs(
        self,
        namespace: Optional[str] = None,
        limit: int = 50
    ) -> dict:
        """
        List recent jobs.

        Args:
            namespace: Optional namespace filter
            limit: Max jobs to return

        Returns:
            Jobs list dict
        """
        client = self._ensure_client()
        params = {"limit": limit}
        if namespace:
            params["namespace"] = namespace
        response = await client.get("/api/jobs", params=params)
        self._handle_error(response)
        return response.json()

    # Conversation endpoints

    async def get_conversation(self, thread_id: str) -> dict:
        """
        Get conversation history.

        Args:
            thread_id: Conversation thread identifier

        Returns:
            Conversation history dict
        """
        client = self._ensure_client()
        response = await client.get(f"/api/conversation/{thread_id}")
        self._handle_error(response)
        return response.json()

    async def delete_conversation(self, thread_id: str) -> dict:
        """
        Clear conversation history.

        Args:
            thread_id: Conversation thread identifier

        Returns:
            Deletion confirmation dict
        """
        client = self._ensure_client()
        response = await client.delete(f"/api/conversation/{thread_id}")
        self._handle_error(response)
        return response.json()


def get_client() -> BackendClient:
    """
    Get a new BackendClient instance.

    Usage:
        async with get_client() as client:
            result = await client.query("search term")

    Returns:
        New BackendClient instance
    """
    return BackendClient()
