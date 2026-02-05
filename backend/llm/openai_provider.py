"""OpenAI LLM provider implementation."""

import os
from typing import AsyncGenerator, Optional

from openai import AsyncOpenAI, RateLimitError, APIError

from backend.llm.base import BaseLLMProvider
import logging

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider."""

    DEFAULT_MODEL = "gpt-4o"
    AVAILABLE_MODELS = ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        super().__init__(model, api_key)
        self._client: Optional[AsyncOpenAI] = None

    @property
    def name(self) -> str:
        return "openai"

    def _get_client(self) -> AsyncOpenAI:
        """Get or create OpenAI client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError("OpenAI API key not configured")
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    def get_default_model(self) -> str:
        return self.DEFAULT_MODEL

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> str:
        """Send chat request to OpenAI."""
        client = self._get_client()
        model = self.model or self.DEFAULT_MODEL

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False
            )
            return response.choices[0].message.content

        except RateLimitError as e:
            logger.error(f"OpenAI rate limit: {e}")
            raise
        except APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """Stream chat response from OpenAI."""
        client = self._get_client()
        model = self.model or self.DEFAULT_MODEL

        try:
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

        except RateLimitError as e:
            logger.error(f"OpenAI rate limit: {e}")
            raise
        except APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
