"""Anthropic Claude LLM provider implementation."""

import os
from typing import AsyncGenerator, Optional

try:
    from anthropic import AsyncAnthropic, RateLimitError, APIError
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from backend.llm.base import BaseLLMProvider
import logging

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider."""

    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
    AVAILABLE_MODELS = [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229"
    ]

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        super().__init__(model, api_key)
        self._client = None

    @property
    def name(self) -> str:
        return "anthropic"

    def _get_client(self):
        """Get or create Anthropic client."""
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

        if self._client is None:
            if not self.api_key:
                raise ValueError("Anthropic API key not configured")
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    def get_default_model(self) -> str:
        return self.DEFAULT_MODEL

    def is_available(self) -> bool:
        return ANTHROPIC_AVAILABLE and bool(self.api_key)

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> str:
        """Send chat request to Anthropic."""
        client = self._get_client()
        model = self.model or self.DEFAULT_MODEL
        max_tokens = max_tokens or 4096

        # Convert messages to Anthropic format
        system_msg = None
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        try:
            response = await client.messages.create(
                model=model,
                messages=chat_messages,
                system=system_msg,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.content[0].text

        except RateLimitError as e:
            logger.error(f"Anthropic rate limit: {e}")
            raise
        except APIError as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """Stream chat response from Anthropic."""
        client = self._get_client()
        model = self.model or self.DEFAULT_MODEL
        max_tokens = max_tokens or 4096

        # Convert messages
        system_msg = None
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        try:
            async with client.messages.stream(
                model=model,
                messages=chat_messages,
                system=system_msg,
                temperature=temperature,
                max_tokens=max_tokens
            ) as stream:
                async for text in stream.text_stream:
                    yield text

        except RateLimitError as e:
            logger.error(f"Anthropic rate limit: {e}")
            raise
        except APIError as e:
            logger.error(f"Anthropic API error: {e}")
            raise
