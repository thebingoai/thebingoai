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
    """Anthropic Claude provider for chat completions."""

    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
    AVAILABLE_MODELS = [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229"
    ]

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        """
        Initialize Anthropic provider.

        Args:
            model: Model name to use
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        super().__init__(model, api_key)
        self._client = None

    @property
    def name(self) -> str:
        """Provider name identifier."""
        return "anthropic"

    def _get_client(self) -> "AsyncAnthropic":
        """
        Get or create Anthropic client.

        Returns:
            AsyncAnthropic client instance

        Raises:
            ImportError: If anthropic package is not installed
            ValueError: If API key is not configured
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

        if self._client is None:
            if not self.api_key:
                raise ValueError("Anthropic API key not configured")
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    def get_default_model(self) -> str:
        """Get default model name."""
        return self.DEFAULT_MODEL

    def is_available(self) -> bool:
        """
        Check if provider is available.

        Returns:
            True if anthropic package is installed and API key is configured
        """
        return ANTHROPIC_AVAILABLE and bool(self.api_key)

    def _convert_messages(self, messages: list[dict]) -> tuple[Optional[str], list[dict]]:
        """
        Convert messages from OpenAI format to Anthropic format.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            (system_message, chat_messages) tuple
        """
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

        return system_msg, chat_messages

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> str:
        """
        Send chat request to Anthropic.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 - 1.0)
            max_tokens: Optional max tokens to generate
            stream: Ignored (use chat_stream for streaming)

        Returns:
            Generated text response

        Raises:
            RateLimitError: If rate limit is exceeded
            APIError: If API request fails
        """
        client = self._get_client()
        model = self.model or self.DEFAULT_MODEL
        max_tokens = max_tokens or 4096

        system_msg, chat_messages = self._convert_messages(messages)

        response = await client.messages.create(
            model=model,
            messages=chat_messages,
            system=system_msg,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.content[0].text

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat response from Anthropic.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 - 1.0)
            max_tokens: Optional max tokens to generate

        Yields:
            Chunks of generated text

        Raises:
            RateLimitError: If rate limit is exceeded
            APIError: If API request fails
        """
        client = self._get_client()
        model = self.model or self.DEFAULT_MODEL
        max_tokens = max_tokens or 4096

        system_msg, chat_messages = self._convert_messages(messages)

        async with client.messages.stream(
            model=model,
            messages=chat_messages,
            system=system_msg,
            temperature=temperature,
            max_tokens=max_tokens
        ) as stream:
            async for text in stream.text_stream:
                yield text
