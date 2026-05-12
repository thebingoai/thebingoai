from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from backend.vectordb.qdrant import ensure_collection
from backend.api import routes
from backend.api.websocket import router as ws_router
from backend.data_plane.errors import NoPlaneProvisionedError
from backend.logging_config import setup_logging
from backend.api import health as health_module
from backend.config import settings
import logging

# Setup logging
setup_logging(level=settings.log_level)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    # Startup
    logger.info("Starting BINGO Backend...")

    # Fail fast in production if the data-plane lockdown is half-configured.
    from backend.services.data_plane_service import check_internal_gcp_config
    check_internal_gcp_config()

    try:
        ensure_collection(settings.qdrant_documents_collection, settings.qdrant_vector_size)
        ensure_collection(settings.qdrant_memories_collection, settings.qdrant_vector_size)
        logger.info("Qdrant collections ready")
    except Exception as e:
        logger.warning(f"Qdrant initialization failed (continuing): {e}")

    # Plugin discovery and loading
    from backend.plugins.loader import discover_and_load_plugins, get_plugin_routers, shutdown_plugins
    discover_and_load_plugins()
    for router, prefix in get_plugin_routers():
        app.include_router(router, prefix=prefix)

    # Backfill profiling for existing connections (runs once after deploy)
    try:
        from backend.tasks.profiling_tasks import backfill_profile_all_connections
        backfill_profile_all_connections.delay()
    except Exception:
        logger.warning("Failed to queue backfill profiling task", exc_info=True)

    # Phase 6: lineage cache invalidation subscriber
    try:
        from backend.lineage.cache import start_subscriber as _start_lineage_subscriber
        _start_lineage_subscriber()
    except Exception:
        logger.warning("Failed to start lineage cache subscriber", exc_info=True)

    yield
    # Shutdown
    logger.info("Shutting down...")
    try:
        from backend.lineage.cache import stop_subscriber as _stop_lineage_subscriber
        _stop_lineage_subscriber()
    except Exception:
        pass
    shutdown_plugins()

app = FastAPI(
    title="BINGO Backend",
    description="Backend for indexing and querying markdown files with LLMs",
    version=settings.app_version,
    lifespan=lifespan
)

# Configure CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_allowed_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(NoPlaneProvisionedError)
async def _no_plane_provisioned_handler(_: Request, exc: NoPlaneProvisionedError):
    return JSONResponse(
        status_code=503,
        content={
            "detail": str(exc),
            "code": "no_data_plane",
            "scope_kind": exc.scope.kind,
            "scope_id": exc.scope.id,
        },
    )


app.include_router(routes.router, prefix="/api")
app.include_router(ws_router)  # WebSocket at /ws (no /api prefix — WS upgrade bypasses proxy)

@app.get("/health")
async def health_check():
    """Basic health check."""
    return {"status": "healthy"}

@app.get("/health/detailed")
async def health_detailed_endpoint():
    """Detailed health check."""
    return await health_module.health_detailed()
