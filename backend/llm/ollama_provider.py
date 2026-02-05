"""Ollama local LLM provider implementation."""

import os
from typing import AsyncGenerator, Optional

import httpx

from backend.llm.base import BaseLLMProvider
from backend.config import settings
import logging

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider."""

    DEFAULT_MODEL = "llama3.2"
    DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        # Ollama doesn't need API key
        super().__init__(model, None)
        self.base_url = settings.ollama_base_url or self.DEFAULT_BASE_URL
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def name(self) -> str:
        return "ollama"

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=120.0)
        return self._client

    def get_default_model(self) -> str:
        return self.DEFAULT_MODEL

    def is_available(self) -> bool:
        """Check if Ollama is running."""
        import asyncio
        try:
            # Quick check - don't block
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return True  # Assume available, will fail on actual request if not

            result = loop.run_until_complete(self._check_available())
            return result
        except Exception:
            return False

    async def _check_available(self) -> bool:
        """Async check if Ollama is available."""
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
        """Send chat request to Ollama."""
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

        try:
            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]

        except httpx.HTTPError as e:
            logger.error(f"Ollama HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """Stream chat response from Ollama."""
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

        try:
            async with client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            import json
                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                yield data["message"]["content"]
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

        except httpx.HTTPError as e:
            logger.error(f"Ollama HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise

    async def list_models(self) -> list[str]:
        """List available Ollama models."""
        client = self._get_client()
        try:
            response = await client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []
