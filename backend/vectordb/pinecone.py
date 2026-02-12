"""Pinecone vector database operations with logging."""

from pinecone import Pinecone, ServerlessSpec
from typing import Optional
from backend.config import settings
import asyncio
import logging

logger = logging.getLogger(__name__)

# Module-level cached instances
_pc: Optional[Pinecone] = None
_index = None


def init_pinecone() -> None:
    """
    Initialize Pinecone client and ensure index exists.

    Creates the index if it doesn't exist, otherwise connects to existing.

    Raises:
        PineconeException: If index creation fails
    """
    global _pc, _index

    logger.debug("Initializing Pinecone client")
    _pc = Pinecone(api_key=settings.pinecone_api_key)

    # Check if index exists
    existing_indexes = [idx.name for idx in _pc.list_indexes()]
    logger.debug(f"Existing indexes: {existing_indexes}")

    if settings.pinecone_index_name not in existing_indexes:
        logger.info(f"Creating Pinecone index: {settings.pinecone_index_name}")
        logger.debug(f"Dimension: {settings.embedding_dimensions}, Region: {settings.pinecone_environment}")
        _pc.create_index(
            name=settings.pinecone_index_name,
            dimension=settings.embedding_dimensions,
            metric=settings.pinecone_similarity_metric,
            spec=ServerlessSpec(
                cloud=settings.pinecone_cloud_provider,
                region=settings.pinecone_environment
            )
        )
        logger.info(f"Index {settings.pinecone_index_name} created successfully")
    else:
        logger.debug(f"Index {settings.pinecone_index_name} already exists")

    _index = _pc.Index(settings.pinecone_index_name)
    logger.info(f"Connected to Pinecone index: {settings.pinecone_index_name}")


def get_index():
    """
    Get Pinecone index, initializing if needed.

    Returns:
        Pinecone Index instance
    """
    global _index
    if _index is None:
        init_pinecone()
    return _index


async def upsert_vectors(
    vectors: list[dict],
    namespace: str = "default",
    batch_size: int = None
) -> dict:
    """
    Upsert vectors to Pinecone.

    Args:
        vectors: List of {"id": str, "values": list[float], "metadata": dict}
        namespace: Target namespace for upsert
        batch_size: Vectors per upsert call (max 100 for Pinecone)

    Returns:
        {"upserted_count": int} - Total vectors upserted
    """
    batch_size = batch_size or settings.pinecone_upsert_batch_size
    logger.debug(f"Upserting {len(vectors)} vectors to namespace '{namespace}'")
    index = get_index()
    total_upserted = 0

    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(vectors) + batch_size - 1) // batch_size

        # Format for Pinecone
        upsert_data = [
            {
                "id": v["id"],
                "values": v["values"],
                "metadata": v.get("metadata", {})
            }
            for v in batch
        ]

        logger.debug(f"Upserting batch {batch_num}/{total_batches} ({len(batch)} vectors)")
        # Wrap blocking Pinecone call with asyncio.to_thread
        response = await asyncio.to_thread(index.upsert, vectors=upsert_data, namespace=namespace)
        total_upserted += response.upserted_count

    logger.info(f"Upserted {total_upserted} vectors to namespace '{namespace}'")
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

    Args:
        query_embedding: Query vector (embedding)
        namespace: Namespace to search
        top_k: Number of results to return
        filter: Optional metadata filter
        include_metadata: Whether to include metadata in results

    Returns:
        List of {"id", "score", "metadata"} dicts
    """
    logger.debug(f"Querying namespace '{namespace}' with top_k={top_k}")
    index = get_index()

    # Wrap blocking Pinecone call with asyncio.to_thread
    response = await asyncio.to_thread(
        index.query,
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

    logger.debug(f"Query returned {len(results)} results")
    if results:
        logger.debug(f"Top result: {results[0]['id']} (score: {results[0]['score']:.4f})")

    return results


async def get_index_stats() -> dict:
    """
    Get index statistics.

    Returns:
        Dict with total_vector_count, dimension, and namespaces
    """
    logger.debug("Fetching index stats")
    index = get_index()

    # Wrap blocking Pinecone call with asyncio.to_thread
    stats = await asyncio.to_thread(index.describe_index_stats)

    result = {
        "total_vector_count": stats.total_vector_count,
        "dimension": stats.dimension,
        "namespaces": {
            ns: {"vector_count": data.vector_count}
            for ns, data in stats.namespaces.items()
        }
    }

    logger.debug(
        f"Index stats: {result['total_vector_count']} total vectors, "
        f"{len(result['namespaces'])} namespaces"
    )

    return result


# Sync wrappers for Celery tasks
def upsert_vectors_sync(vectors: list[dict], namespace: str = "default") -> dict:
    """
    Synchronous upsert wrapper for Celery tasks.

    Args:
        vectors: List of vector dicts
        namespace: Target namespace

    Returns:
        Upsert result dict
    """
    import asyncio
    return asyncio.run(upsert_vectors(vectors, namespace))
