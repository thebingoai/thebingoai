from backend.agents.skills.base import BaseSkill
from backend.llm.factory import get_llm_provider
from backend.config import settings
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class SummarizeSkill(BaseSkill):
    """Example skill for summarizing text."""

    @property
    def name(self) -> str:
        return "summarize_text"

    @property
    def description(self) -> str:
        return "Summarize a long text into key points. Use when user asks for a summary."

    async def execute(self, text: str) -> Dict[str, Any]:
        """
        Summarize the given text.

        Args:
            text: Text to summarize

        Returns:
            Dict with success, message (summary)
        """
        try:
            # Get LLM provider
            provider = get_llm_provider(settings.default_llm_provider)
            llm = provider.get_langchain_llm()

            # Create summary prompt
            prompt = f"""Please provide a concise summary of the following text in bullet points:

{text}

Summary:"""

            # Generate summary
            response = await llm.ainvoke(prompt)
            summary = response.content if hasattr(response, "content") else str(response)

            return {
                "success": True,
                "message": summary
            }

        except Exception as e:
            logger.error(f"Summarize skill failed: {str(e)}")
            return {
                "success": False,
                "message": f"Summarization failed: {str(e)}"
            }
