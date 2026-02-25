from backend.agents.skills.base import BaseSkill
from backend.agents.skills.registry import SkillRegistry, get_skill_registry
from backend.agents.skills.summarize import SummarizeSkill

# Register built-in skills into the singleton registry
_registry = get_skill_registry()
_registry.register(SummarizeSkill())

__all__ = ["BaseSkill", "SkillRegistry", "get_skill_registry", "SummarizeSkill"]
