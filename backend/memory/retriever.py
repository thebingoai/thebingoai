"""Memory retriever for query generation."""

from backend.memory.storage import MemoryStorage
from typing import List, Dict, Any


class MemoryRetriever:
    """Retrieve relevant memories for query generation."""

    def __init__(self):
        self.storage = MemoryStorage()

    async def get_relevant_context(
        self,
        user_id: str,
        query: str,
        top_k: int = 3
    ) -> str:
        """
        Get relevant memory context for a query.

        Args:
            user_id: User ID
            query: User's query
            top_k: Number of memories to retrieve

        Returns:
            Formatted context string
        """
        memories = await self.storage.retrieve_memories(user_id, query, top_k)

        if not memories:
            return ""

        context_parts = ["=== Relevant Past Interactions ===\n"]

        for i, memory in enumerate(memories, 1):
            context_parts.append(f"{i}. {memory['date']} (relevance: {memory['score']:.2f})")
            context_parts.append(f"   {memory['text']}\n")

        return "\n".join(context_parts)
