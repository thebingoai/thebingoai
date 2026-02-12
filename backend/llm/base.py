"""Base LLM provider interface."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        self._client = None

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> str:
        """
        Send chat messages and get response.

        Args:
            messages: List of {"role": str, "content": str}
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            stream: Whether to stream response

        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat response.

        Args:
            messages: List of {"role": str, "content": str}
            temperature: Sampling temperature
            max_tokens: Max tokens to generate

        Yields:
            Chunks of generated text
        """
        pass

    @abstractmethod
    def get_default_model(self) -> str:
        """Get default model name for this provider."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available (API key set, service reachable)."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @abstractmethod
    def get_langchain_llm(self):
        """
        Get LangChain-compatible LLM instance for use with LangGraph agents.

        Returns:
            LangChain ChatModel instance (ChatOpenAI, ChatAnthropic, ChatOllama)
        """
        pass
