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
    SearchRequest, ScoredPoint
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
) -> None:
    """
    Upsert vectors to Qdrant.

    Args:
        vectors: List of vectors with format:
            [{"id": str, "values": List[float], "metadata": Dict}]
        namespace: Namespace (maps to collection + tenant_id)
    """
    if not vectors:
        return

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


async def query_vectors(
    query_vector: List[float],
    namespace: str = "default",
    top_k: int = 5,
    score_threshold: float = 0.0
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
    collection_name, tenant_id = _namespace_to_collection(namespace)

    client = get_client()

    # Search with tenant filtering
    results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
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
        points_selector=Filter(must=must_conditions)
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
