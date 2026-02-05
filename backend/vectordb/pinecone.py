from pinecone import Pinecone, ServerlessSpec
from typing import Optional
from backend.config import settings
import logging

logger = logging.getLogger(__name__)

_pc: Optional[Pinecone] = None
_index = None

def init_pinecone() -> None:
    """Initialize Pinecone client and ensure index exists."""
    global _pc, _index

    _pc = Pinecone(api_key=settings.pinecone_api_key)

    # Check if index exists
    existing_indexes = [idx.name for idx in _pc.list_indexes()]

    if settings.pinecone_index_name not in existing_indexes:
        logger.info(f"Creating Pinecone index: {settings.pinecone_index_name}")
        _pc.create_index(
            name=settings.pinecone_index_name,
            dimension=settings.embedding_dimensions,
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region=settings.pinecone_environment
            )
        )

    _index = _pc.Index(settings.pinecone_index_name)
    logger.info(f"Connected to Pinecone index: {settings.pinecone_index_name}")

def get_index():
    """Get Pinecone index, initializing if needed."""
    global _index
    if _index is None:
        init_pinecone()
    return _index

async def upsert_vectors(
    vectors: list[dict],
    namespace: str = "default",
    batch_size: int = 100
) -> dict:
    """
    Upsert vectors to Pinecone.

    Args:
        vectors: List of {"id": str, "values": list[float], "metadata": dict}
        namespace: Target namespace
        batch_size: Vectors per upsert call

    Returns:
        {"upserted_count": int}
    """
    index = get_index()
    total_upserted = 0

    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]

        # Format for Pinecone
        upsert_data = [
            {
                "id": v["id"],
                "values": v["values"],
                "metadata": v.get("metadata", {})
            }
            for v in batch
        ]

        response = index.upsert(vectors=upsert_data, namespace=namespace)
        total_upserted += response.upserted_count

    return {"upserted_count": total_upserted}

async def query_vectors(
    query_embedding: list[float],
    namespace: str = "default",
    top_k: int = 5,
    filter: Optional[dict] = None,
    include_metadata: bool = True
) -> list[dict]:
    """
    Query Pinecone for similar vectors.

    Returns:
        List of {"id", "score", "metadata"} dicts
    """
    index = get_index()

    response = index.query(
        vector=query_embedding,
        namespace=namespace,
        top_k=top_k,
        filter=filter,
        include_metadata=include_metadata
    )

    results = []
    for match in response.matches:
        results.append({
            "id": match.id,
            "score": match.score,
            "metadata": match.metadata or {}
        })

    return results

async def delete_vectors(
    ids: list[str] = None,
    namespace: str = "default",
    delete_all: bool = False,
    filter: Optional[dict] = None
) -> dict:
    """Delete vectors by ID, filter, or all in namespace."""
    index = get_index()

    if delete_all:
        index.delete(delete_all=True, namespace=namespace)
    elif ids:
        index.delete(ids=ids, namespace=namespace)
    elif filter:
        index.delete(filter=filter, namespace=namespace)

    return {"deleted": True}

async def get_index_stats() -> dict:
    """Get index statistics."""
    index = get_index()
    stats = index.describe_index_stats()

    return {
        "total_vector_count": stats.total_vector_count,
        "dimension": stats.dimension,
        "namespaces": {
            ns: {"vector_count": data.vector_count}
            for ns, data in stats.namespaces.items()
        }
    }

async def list_namespaces() -> list[str]:
    """List all namespaces in the index."""
    stats = await get_index_stats()
    return list(stats.get("namespaces", {}).keys())


# Sync wrappers for Celery
def upsert_vectors_sync(vectors: list[dict], namespace: str = "default") -> dict:
    """Synchronous upsert."""
    import asyncio
    return asyncio.run(upsert_vectors(vectors, namespace))
