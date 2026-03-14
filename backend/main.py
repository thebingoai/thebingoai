from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.vectordb.qdrant import ensure_collection
from backend.api import routes
from backend.api.websocket import router as ws_router
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
    logger.info("Starting LLM-MD Backend...")
    try:
        ensure_collection(settings.qdrant_documents_collection, settings.qdrant_vector_size)
        ensure_collection(settings.qdrant_memories_collection, settings.qdrant_vector_size)
        logger.info("Qdrant collections ready")
    except Exception as e:
        logger.warning(f"Qdrant initialization failed (continuing): {e}")
    yield
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(
    title="LLM-MD Backend",
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
