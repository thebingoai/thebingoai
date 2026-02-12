"""OpenAI LLM provider implementation."""

import os
from typing import AsyncGenerator, Optional

from openai import AsyncOpenAI, RateLimitError, APIError

from backend.llm.base import BaseLLMProvider
import logging

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider for chat completions."""

    DEFAULT_MODEL = "gpt-4o"
    AVAILABLE_MODELS = ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        """
        Initialize OpenAI provider.

        Args:
            model: Model name to use
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        super().__init__(model, api_key)
        self._client: Optional[AsyncOpenAI] = None

    @property
    def name(self) -> str:
        """Provider name identifier."""
        return "openai"

    def _get_client(self) -> AsyncOpenAI:
        """
        Get or create OpenAI client.

        Returns:
            AsyncOpenAI client instance

        Raises:
            ValueError: If API key is not configured
        """
        if self._client is None:
            if not self.api_key:
                raise ValueError("OpenAI API key not configured")
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    def get_default_model(self) -> str:
        """Get default model name."""
        return self.DEFAULT_MODEL

    def is_available(self) -> bool:
        """
        Check if provider is available.

        Returns:
            True if API key is configured
        """
        return bool(self.api_key)

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> str:
        """
        Send chat request to OpenAI.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 - 2.0)
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

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False
        )
        return response.choices[0].message.content

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat response from OpenAI.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 - 2.0)
            max_tokens: Optional max tokens to generate

        Yields:
            Chunks of generated text

        Raises:
            RateLimitError: If rate limit is exceeded
            APIError: If API request fails
        """
        client = self._get_client()
        model = self.model or self.DEFAULT_MODEL

        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
