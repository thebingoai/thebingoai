from langchain_core.tools import tool
from backend.agents.context import AgentContext
from backend.models.user_memory import UserMemory
from typing import List, Optional, Callable
import json


def build_memory_tools(context: AgentContext, db_session_factory: Optional[Callable] = None) -> List:
    """Build memory management tools for the orchestrator agent."""
    if db_session_factory is None:
        return []

    @tool
    async def save_memory(content: str, category: str = "") -> str:
        """Save an important fact, preference, or pattern to persistent memory.

        Use this when the user mentions something worth remembering across conversations:
        - Preferences: "I prefer concise answers", "always use metric units"
        - Facts: "My team is in Dublin", "I'm a backend engineer"
        - Corrections: "Actually, the main DB is Postgres not MySQL"
        - Workflow patterns: "I usually check sales data on Mondays"

        Do NOT save: transient task details, things already in the conversation,
        or duplicates of existing memories.

        Args:
            content: The fact or preference to remember (1-2 sentences).
            category: Optional category (e.g., "preference", "fact", "workflow").
        """
        db = db_session_factory()
        try:
            count = db.query(UserMemory).filter(
                UserMemory.user_id == context.user_id,
                UserMemory.is_active == True
            ).count()
            if count >= 50:
                return json.dumps({"success": False, "message": "Memory limit reached (50). Delete old memories first."})
            memory = UserMemory(user_id=context.user_id, content=content, category=category or None)
            db.add(memory)
            db.commit()
            return json.dumps({"success": True, "message": f"Remembered: {content}"})
        except Exception as exc:
            db.rollback()
            return json.dumps({"success": False, "message": str(exc)})
        finally:
            db.close()

    return [save_memory]
