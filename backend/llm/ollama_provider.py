"""Ollama local LLM provider implementation."""

from typing import AsyncGenerator, Optional

import httpx

from backend.llm.base import BaseLLMProvider
from backend.config import settings
import logging

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider for running local models."""

    DEFAULT_MODEL = "llama3.2"
    DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        """
        Initialize Ollama provider.

        Args:
            model: Model name to use
            api_key: Ignored (Ollama doesn't require API keys)
        """
        # Ollama doesn't need API key
        super().__init__(model, None)
        self.base_url = settings.ollama_base_url or self.DEFAULT_BASE_URL
        self._client: Optional[httpx.AsyncClient] = None
        self._available: Optional[bool] = None  # Cached availability check

    @property
    def name(self) -> str:
        """Provider name identifier."""
        return "ollama"

    def _get_client(self) -> httpx.AsyncClient:
        """
        Get or create HTTP client.

        Returns:
            HTTP client configured for Ollama API
        """
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=120.0)
        return self._client

    def get_default_model(self) -> str:
        """Get default model name."""
        return self.DEFAULT_MODEL

    def is_available(self) -> bool:
        """
        Check if Ollama service is available.

        Returns:
            True if Ollama is running and accessible, False otherwise

        Note:
            This is a synchronous check that assumes availability.
            Actual verification happens on first async request.
        """
        # We can't reliably do async checks in a sync context
        # Return True and let actual requests fail if Ollama isn't running
        return True

    async def check_available_async(self) -> bool:
        """
        Async check if Ollama service is available.

        Returns:
            True if Ollama is running and responds to /api/tags
        """
        try:
            client = self._get_client()
            response = await client.get("/api/tags", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> str:
        """
        Send chat request to Ollama.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 - 2.0)
            max_tokens: Optional max tokens to generate
            stream: Ignored (use chat_stream for streaming)

        Returns:
            Generated text response

        Raises:
            httpx.HTTPError: If the HTTP request fails
        """
        client = self._get_client()
        model = self.model or self.DEFAULT_MODEL

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        response = await client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat response from Ollama.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 - 2.0)
            max_tokens: Optional max tokens to generate

        Yields:
            Chunks of generated text

        Raises:
            httpx.HTTPError: If the HTTP request fails
        """
        import json

        client = self._get_client()
        model = self.model or self.DEFAULT_MODEL

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature
            }
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        async with client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue

    async def list_models(self) -> list[str]:
        """
        List available Ollama models.

        Returns:
            List of model names available on the Ollama server
        """
        client = self._get_client()
        try:
            response = await client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []
