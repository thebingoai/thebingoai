from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseSkill(ABC):
    """
    Abstract base class for agent skills.

    Skills are specialized tools that can be registered dynamically
    and invoked by the orchestrator when needed.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill name for tool registration."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what the skill does (shown to LLM)."""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the skill with given parameters.

        Returns:
            Dict with success, message, and any additional data
        """
        pass

    def to_tool(self):
        """
        Convert skill to a LangChain StructuredTool.

        Returns a tool wrapping execute() with the skill's name and description.
        """
        from langchain_core.tools import StructuredTool

        return StructuredTool.from_function(
            coroutine=self.execute,
            name=self.name,
            description=self.description,
        )
