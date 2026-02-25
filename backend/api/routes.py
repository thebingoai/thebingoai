from fastapi import APIRouter
from backend.api import upload, query, health, jobs, auth, connections, usage, chat, memory, sql_query
from backend.api import feature_config
from backend.config import settings

router = APIRouter()

# Authentication
router.include_router(auth.router)

# Database Connections
router.include_router(connections.router)

# Direct SQL Query Execution
router.include_router(sql_query.router)

# Chat with Orchestrator (Phase 05)
router.include_router(chat.router)

# Memory System (Phase 06)
router.include_router(memory.router)

# Usage Tracking (Phase 07)
router.include_router(usage.router)

# Feature config (always available so frontend can check flags)
router.include_router(feature_config.router)

# Enterprise: Org/Team/Policy/Agent routes (Phase 1-3)
if settings.enable_governance:
    from backend.api import organizations, teams, policies, agents as custom_agents
    router.include_router(organizations.router)
    router.include_router(teams.router)
    router.include_router(policies.router)
    router.include_router(custom_agents.router)

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
