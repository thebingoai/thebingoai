from typing import Dict, List
from backend.agents.skills.base import BaseSkill
import logging

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Registry for dynamically loading and managing agent skills.

    Skills can be registered at startup or runtime and converted
    to LangChain tools for orchestrator use.
    """

    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill):
        """Register a skill."""
        self._skills[skill.name] = skill
        logger.info(f"Registered skill: {skill.name}")

    def get(self, name: str) -> BaseSkill:
        """Get a skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> List[str]:
        """List all registered skill names."""
        return list(self._skills.keys())

    def to_tools(self) -> List:
        """Convert all registered skills to LangChain tools."""
        return [skill.to_tool() for skill in self._skills.values()]


# Global skill registry
_global_registry = SkillRegistry()


def get_skill_registry() -> SkillRegistry:
    """Get the global skill registry."""
    return _global_registry
