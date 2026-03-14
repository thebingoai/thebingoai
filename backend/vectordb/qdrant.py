"""Qdrant vector database client for RAG and memory storage.

Two collections:
- documents: RAG document embeddings (replaces Pinecone)
- memories: Daily interaction summaries for memory system

Tenant isolation via indexed tenant_id payload field.
"""

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue,
    FilterSelector, SearchRequest, ScoredPoint,
    PayloadSelectorInclude
)
from backend.config import settings
from typing import List, Dict, Any, Optional
import logging
import uuid

logger = logging.getLogger(__name__)


class QdrantClientSingleton:
    """Singleton Qdrant client."""
    _instance: Optional[QdrantClient] = None

    @classmethod
    def get_client(cls) -> QdrantClient:
        """Get or create Qdrant client instance."""
        if cls._instance is None:
            cls._instance = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key if settings.qdrant_api_key else None,
                timeout=30.0
            )
            logger.info(f"Connected to Qdrant at {settings.qdrant_url}")
        return cls._instance


def get_client() -> QdrantClient:
    """Get Qdrant client."""
    return QdrantClientSingleton.get_client()


def ensure_collection(collection_name: str, vector_size: int = 3072):
    """
    Ensure collection exists with proper configuration.

    Args:
        collection_name: Name of the collection
        vector_size: Dimension of vectors (default: 3072 for text-embedding-3-large)
    """
    client = get_client()

    # Check if collection exists
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]

    if collection_name not in collection_names:
        logger.info(f"Creating Qdrant collection: {collection_name}")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE
            )
        )

        # Create index on tenant_id for fast filtering
        client.create_payload_index(
            collection_name=collection_name,
            field_name="tenant_id",
            field_schema="keyword"
        )
        logger.info(f"Created collection {collection_name} with tenant_id index")


def _namespace_to_collection(namespace: str) -> tuple[str, str]:
    """
    Map namespace to collection and tenant_id.

    Pinecone namespace compatibility layer:
    - "memory:user-<id>" → collection: memories, tenant_id: <id>
    - Other namespaces → collection: documents, tenant_id: namespace

    Args:
        namespace: Namespace string

    Returns:
        Tuple of (collection_name, tenant_id)
    """
    if namespace.startswith("memory:user-"):
        tenant_id = namespace.replace("memory:user-", "")
        return settings.qdrant_memories_collection, tenant_id
    else:
        return settings.qdrant_documents_collection, namespace


async def upsert_vectors(
    vectors: List[Dict[str, Any]],
    namespace: str = "default"
) -> Dict[str, Any]:
    """
    Upsert vectors to Qdrant.

    Args:
        vectors: List of vectors with format:
            [{"id": str, "values": List[float], "metadata": Dict}]
        namespace: Namespace (maps to collection + tenant_id)
    """
    if not vectors:
        return {"upserted_count": 0}

    collection_name, tenant_id = _namespace_to_collection(namespace)
    ensure_collection(collection_name)

    client = get_client()

    # Convert to Qdrant points
    points = []
    for vec in vectors:
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, vec["id"]))  # Deterministic UUID
        payload = vec.get("metadata", {}).copy()
        payload["tenant_id"] = tenant_id
        payload["original_id"] = vec["id"]

        points.append(PointStruct(
            id=point_id,
            vector=vec["values"],
            payload=payload
        ))

    # Batch upsert
    client.upsert(
        collection_name=collection_name,
        points=points
    )

    logger.info(f"Upserted {len(points)} vectors to {collection_name} (tenant: {tenant_id})")
    return {"upserted_count": len(points)}


async def query_vectors(
    query_vector: Optional[List[float]] = None,
    namespace: str = "default",
    top_k: int = 5,
    score_threshold: float = 0.0,
    query_embedding: Optional[List[float]] = None,
    filter: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Query vectors from Qdrant.

    Args:
        query_vector: Query embedding
        namespace: Namespace (maps to collection + tenant_id)
        top_k: Number of results
        score_threshold: Minimum similarity score

    Returns:
        List of matches with format:
            [{"id": str, "score": float, "metadata": Dict}]
    """
    # Support query_embedding as alias for query_vector
    vec = query_embedding if query_embedding is not None else query_vector

    collection_name, tenant_id = _namespace_to_collection(namespace)

    client = get_client()

    # Search with tenant filtering
    results = client.search(
        collection_name=collection_name,
        query_vector=vec,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="tenant_id",
                    match=MatchValue(value=tenant_id)
                )
            ]
        ),
        limit=top_k,
        score_threshold=score_threshold if score_threshold > 0 else None
    )

    # Convert to common format
    matches = []
    for hit in results:
        matches.append({
            "id": hit.payload.get("original_id", str(hit.id)),
            "score": hit.score,
            "metadata": {k: v for k, v in hit.payload.items()
                       if k not in ["tenant_id", "original_id"]}
        })

    return matches


async def delete_by_filter(
    collection: str,
    filter: Dict[str, str]
) -> None:
    """
    Delete vectors by metadata filter.

    Args:
        collection: Collection name
        filter: Filter dict (e.g., {"tenant_id": "user123"})
    """
    client = get_client()

    # Build Qdrant filter
    must_conditions = []
    for key, value in filter.items():
        must_conditions.append(
            FieldCondition(
                key=key,
                match=MatchValue(value=value)
            )
        )

    client.delete(
        collection_name=collection,
        points_selector=FilterSelector(filter=Filter(must=must_conditions))
    )

    logger.info(f"Deleted vectors from {collection} with filter {filter}")


async def delete_namespace(namespace: str) -> None:
    """
    Delete all vectors in a namespace.

    Args:
        namespace: Namespace to delete
    """
    collection_name, tenant_id = _namespace_to_collection(namespace)
    await delete_by_filter(collection_name, {"tenant_id": tenant_id})


def scroll_all_points(
    collection: str,
    tenant_id: str,
    payload_fields: List[str]
) -> List[Dict[str, Any]]:
    """
    Scroll through all points for a tenant, returning only requested payload fields.

    Args:
        collection: Collection name
        tenant_id: Tenant ID to filter by
        payload_fields: List of payload field names to return

    Returns:
        List of payload dicts for all matching points
    """
    client = get_client()

    tenant_filter = Filter(
        must=[
            FieldCondition(
                key="tenant_id",
                match=MatchValue(value=tenant_id)
            )
        ]
    )

    results = []
    offset = None
    batch_size = 256

    while True:
        points, next_offset = client.scroll(
            collection_name=collection,
            scroll_filter=tenant_filter,
            limit=batch_size,
            offset=offset,
            with_payload=PayloadSelectorInclude(include=payload_fields),
            with_vectors=False,
        )

        for point in points:
            results.append(point.payload or {})

        if next_offset is None:
            break
        offset = next_offset

    logger.info(f"Scrolled {len(results)} points from {collection} (tenant: {tenant_id})")
    return results


def upsert_vectors_sync(
    vectors: List[Dict[str, Any]],
    namespace: str = "default"
) -> Dict[str, Any]:
    """Sync wrapper for upsert_vectors (used by Celery tasks)."""
    import asyncio
    return asyncio.run(upsert_vectors(vectors, namespace))


async def get_collection_stats() -> Dict[str, Any]:
    """
    Get collection statistics (replaces Pinecone get_index_stats).

    Returns:
        Dict with total_vector_count, dimension, and namespaces keys
    """
    client = get_client()
    try:
        info = client.get_collection(settings.qdrant_documents_collection)
        count = info.vectors_count or 0
        return {
            "total_vector_count": count,
            "dimension": settings.qdrant_vector_size,
            "namespaces": {}
        }
    except Exception as e:
        logger.error(f"Failed to get collection stats: {e}")
        return {"total_vector_count": 0, "dimension": settings.qdrant_vector_size, "namespaces": {}}


def health_check() -> bool:
    """
    Check Qdrant connection health.

    Returns:
        True if connection is healthy
    """
    try:
        client = get_client()
        collections = client.get_collections()
        return True
    except Exception as e:
        logger.error(f"Qdrant health check failed: {str(e)}")
        return False
