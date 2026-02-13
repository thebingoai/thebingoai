from fastapi import APIRouter
from backend.api import upload, query, health, jobs, auth, connections, usage, chat
# Memory temporarily disabled due to LangChain dependency conflicts

router = APIRouter()

# Authentication
router.include_router(auth.router)

# Database Connections
router.include_router(connections.router)

# Chat with Orchestrator (Phase 05)
router.include_router(chat.router)

# Memory System (Phase 06) - TEMPORARILY DISABLED
# router.include_router(memory.router)

# Usage Tracking (Phase 07)
router.include_router(usage.router)

# Upload
router.post("/upload", tags=["upload"])(upload.upload_file)

# Query
router.post("/query", tags=["query"])(query.query)
router.get("/search", tags=["query"])(query.search)

# Status
router.get("/status", tags=["status"])(health.get_status)

# Jobs
router.get("/jobs", tags=["jobs"])(jobs.list_all_jobs)
router.get("/jobs/{job_id}", tags=["jobs"])(jobs.get_job_status)
