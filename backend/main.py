from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.vectordb.pinecone import init_pinecone
from backend.api import routes
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
    init_pinecone()
    logger.info("Pinecone initialized")
    yield
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(
    title="LLM-MD Backend",
    description="Backend for indexing and querying markdown files with LLMs",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Nuxt dev server
        "http://localhost:5173",  # Vite dev server (alternative)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router, prefix="/api")

@app.get("/health")
async def health():
    """Basic health check."""
    return {"status": "healthy"}

@app.get("/health/detailed")
async def health_detailed_endpoint():
    """Detailed health check."""
    return await health_module.health_detailed()
