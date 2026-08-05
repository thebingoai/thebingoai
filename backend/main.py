from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from backend.vectordb.qdrant import ensure_collection
from backend.api import routes
from backend.api.websocket import router as ws_router
from backend.data_plane.errors import NoPlaneProvisionedError
from sqlalchemy.exc import OperationalError, TimeoutError as SQLTimeoutError
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

    # Stall watchdog: logs the blocking stack whenever the event loop freezes
    # (>5s), so probe-kill incidents leave evidence of the culprit frame.
    from backend.services.loop_watchdog import start as start_loop_watchdog
    start_loop_watchdog()

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

    # Verify provision-on-miss is wired up after plugin load (fail fast under lockdown)
    if getattr(settings, "disable_local_data_plane", False):
        from backend.services.data_plane_service import _provision_on_miss
        if _provision_on_miss is None:
            raise RuntimeError(
                "DISABLE_LOCAL_DATA_PLANE=true but no plane provisioner registered. "
                "bingo-admin plugin on_startup must call register_plane_provisioner()."
            )

    # Provision the ONE shared Airbnb sample (system org + Parquet) once the
    # plane provisioner is wired up. Best-effort — never block boot.
    try:
        from backend.database.session import SessionLocal
        from backend.services.seed import ensure_shared_sample
        with SessionLocal() as db:
            ensure_shared_sample(db)
    except Exception:
        logger.warning("Shared sample provisioning failed", exc_info=True)

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

    # Template backfill (core connectors + every plugin) does live source-DB
    # introspection per connection — slow, and dead/misconfigured connections
    # stall the event loop for their full connect timeout. Run it off the startup
    # critical path on a thread so uvicorn serves /health immediately and
    # readiness never waits on external DBs. Daemon, so a mid-flight backfill
    # never delays process exit: the work is idempotent, self-gated by
    # settings.template_backfill_on_startup, and reruns on the next boot.
    # run_startup_backfill single-flights across replicas and swallows+logs its
    # own failures — nothing to await or cancel here.
    import threading
    from backend.services.template_materializer import run_startup_backfill
    threading.Thread(
        target=run_startup_backfill, daemon=True, name="template-backfill",
    ).start()

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


@app.exception_handler(SQLTimeoutError)
async def _pool_exhausted_handler(_: Request, exc: SQLTimeoutError):
    """Client-side pool checkout timed out (db_pool_timeout).

    Shed the request instead of letting it surface as a 500 with a stack trace.
    Nothing else in the backend catches this, so before it existed pool
    exhaustion was indistinguishable from an application bug in the logs.
    Retry-After is deliberately short: the pool frees up on the scale of a
    request, not a deploy.
    """
    logger.warning("DB pool exhausted, shedding request: %s", exc)
    return JSONResponse(
        status_code=503,
        headers={"Retry-After": "2"},
        content={
            "detail": "Database is busy, please retry.",
            "code": "db_pool_exhausted",
        },
    )


@app.exception_handler(OperationalError)
async def _db_unavailable_handler(_: Request, exc: OperationalError):
    """Connection-level DB failure — the server side of the same problem.

    When PgBouncer hits max_client_conn it refuses the connection outright,
    which arrives as OperationalError rather than a checkout TimeoutError; same
    incident, different layer. Logged at error with the traceback so a genuine
    misconfiguration (bad credentials, missing database) is still diagnosable
    rather than hidden behind a friendly retry message.
    """
    logger.error("Database unavailable, shedding request", exc_info=exc)
    return JSONResponse(
        status_code=503,
        headers={"Retry-After": "5"},
        content={
            "detail": "Database is temporarily unavailable, please retry.",
            "code": "db_unavailable",
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
