from backend.models.responses import StatusResponse, IndexStats
from backend.vectordb.qdrant import get_collection_stats, health_check as qdrant_health_check
from backend.config import settings
import redis

async def get_status() -> StatusResponse:
    """Get index statistics."""
    stats = await get_collection_stats()

    return StatusResponse(
        status="healthy",
        index=IndexStats(
            name=settings.qdrant_documents_collection,
            total_vectors=stats.get("total_vector_count", 0),
            dimension=stats.get("dimension", settings.embedding_dimensions),
            namespaces=stats.get("namespaces", {})
        ),
        embedding_model=settings.embedding_model
    )

async def health_detailed() -> dict:
    """Detailed health check."""
    checks = {"api": "healthy", "redis": "unknown", "qdrant": "unknown"}

    # Check Redis
    try:
        r = redis.from_url(settings.redis_url)
        r.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Redis check failed: {e}", exc_info=True)
        checks["redis"] = "unhealthy"

    # Check Qdrant
    try:
        if qdrant_health_check():
            checks["qdrant"] = "healthy"
        else:
            checks["qdrant"] = "unhealthy"
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Qdrant check failed: {e}", exc_info=True)
        checks["qdrant"] = "unhealthy"

    overall = "healthy" if all(
        v == "healthy" or isinstance(v, int)
        for v in checks.values()
    ) else "degraded"

    return {"status": overall, "checks": checks}


async def app_info() -> dict:
    """Return application edition, version, and loaded plugins."""
    from backend.plugins.loader import get_loaded_plugins

    plugins = get_loaded_plugins()
    edition = "Enterprise" if plugins else "Community"
    return {
        "edition": edition,
        "version": "1.2.7",
        "plugins": [{"name": p.name, "version": p.version} for p in plugins.values()],
    }
