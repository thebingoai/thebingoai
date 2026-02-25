"""Memory storage in Qdrant."""

from backend.vectordb.qdrant import upsert_vectors, query_vectors, delete_by_filter, scroll_all_points
from backend.embedder.openai import OpenAIEmbedder
from backend.config import settings
from typing import List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MemoryStorage:
    """Store and retrieve memories from Qdrant via shared vectordb module."""

    def __init__(self):
        self.embedder = OpenAIEmbedder()

    async def store_memory(
        self,
        user_id: str,
        memory_text: str,
        date: datetime,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Store a memory in Qdrant memories collection.

        Args:
            user_id: User ID
            memory_text: Memory summary text
            date: Date of the memory
            metadata: Additional metadata

        Returns:
            Memory ID
        """
        embedding = await self.embedder.embed_text(memory_text)
        memory_id = f"memory:{user_id}:{date.strftime('%Y-%m-%d')}"

        # Use namespace pattern — qdrant module routes to memories collection
        namespace = f"memory:user-{user_id}"

        vectors = [{
            "id": memory_id,
            "values": embedding,
            "metadata": {
                "user_id": user_id,
                "memory_text": memory_text,
                "date": date.isoformat(),
                **metadata
            }
        }]

        await upsert_vectors(vectors, namespace=namespace)
        logger.info(f"Stored memory {memory_id} for user {user_id}")
        return memory_id

    async def retrieve_memories(
        self,
        user_id: str,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant memories via semantic search.

        Args:
            user_id: User ID
            query: Search query
            top_k: Number of results

        Returns:
            List of memories
        """
        query_embedding = await self.embedder.embed_text(query)
        namespace = f"memory:user-{user_id}"

        results = await query_vectors(query_embedding, namespace=namespace, top_k=top_k)

        memories = []
        for match in results:
            memories.append({
                "id": match["id"],
                "score": match["score"],
                "text": match["metadata"].get("memory_text", ""),
                "date": match["metadata"].get("date"),
                "metadata": {k: v for k, v in match["metadata"].items()
                           if k not in ["memory_text", "date", "user_id"]}
            })

        logger.info(f"Retrieved {len(memories)} memories for user {user_id}")
        return memories

    def list_memory_dates(self, user_id: str) -> List[Dict[str, Any]]:
        """
        List all memory dates and conversation counts for a user.

        Args:
            user_id: User ID

        Returns:
            List of dicts with 'date' (YYYY-MM-DD) and 'count' (query_count)
        """
        points = scroll_all_points(
            collection=settings.qdrant_memories_collection,
            tenant_id=user_id,
            payload_fields=["date", "query_count"]
        )

        result = []
        for payload in points:
            raw_date = payload.get("date", "")
            date_str = raw_date[:10] if raw_date else ""
            if date_str:
                result.append({
                    "date": date_str,
                    "count": payload.get("query_count", 1)
                })

        return result

    async def delete_user_memories(self, user_id: str):
        """
        Delete all memories for a user.

        Args:
            user_id: User ID
        """
        await delete_by_filter(
            collection=settings.qdrant_memories_collection,
            filter={"tenant_id": user_id}
        )
        logger.info(f"Deleted all memories for user {user_id}")
