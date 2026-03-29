"""OpenAI LLM provider implementation."""

from typing import AsyncGenerator, Optional

from openai import AsyncOpenAI, RateLimitError, APIError
from langchain_openai import ChatOpenAI

from backend.llm.base import BaseLLMProvider
from backend.config import settings
import logging

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider for chat completions."""

    AVAILABLE_MODELS = ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        """
        Initialize OpenAI provider.

        Args:
            model: Model name to use
            api_key: OpenAI API key (defaults to settings)
        """
        api_key = api_key or settings.openai_api_key
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
        return settings.openai_default_model

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
        model = self.model or settings.openai_default_model

        kwargs = dict(model=model, messages=messages, temperature=temperature, stream=False)
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        response = await client.chat.completions.create(**kwargs)
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
        model = self.model or settings.openai_default_model

        kwargs = dict(model=model, messages=messages, temperature=temperature, stream=True)
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        stream = await client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def get_langchain_llm(self) -> ChatOpenAI:
        """
        Get LangChain-compatible ChatOpenAI instance.

        Returns:
            ChatOpenAI instance configured for this provider
        """
        model = self.model or self.get_default_model()
        return ChatOpenAI(
            model=model,
            api_key=self.api_key,
            temperature=0
        )
