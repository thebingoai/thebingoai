from fastapi import APIRouter
from backend.api import upload, query, health, jobs, auth, connections, usage, chat, memory, sql_query, chat_files, sqlite_upload, credits
from backend.api import agents as custom_agents, skills, heartbeat_jobs, dashboards, widget_data, dashboard_schedule
from backend.api import feature_config
from backend.auth.webhooks import router as webhook_router
from backend.api import query_results, agent_sessions

router = APIRouter()

# Authentication
router.include_router(auth.router)

# SSO Webhooks
router.include_router(webhook_router)

# Database Connections
router.include_router(connections.router)

# SQLite Upload
router.include_router(sqlite_upload.router)

# Direct SQL Query Execution
router.include_router(sql_query.router)

# Chat with Orchestrator (Phase 05)
router.include_router(chat.router)

# Chat File Upload
router.include_router(chat_files.router)

# Memory System (Phase 06)
router.include_router(memory.router)

# Usage Tracking (Phase 07)
router.include_router(usage.router)

# Credits Balance
router.include_router(credits.router)

# Enterprise: Custom Agent Registry (Phase 3)
router.include_router(custom_agents.router)

# User Skills
router.include_router(skills.router)

# Heartbeat Jobs
router.include_router(heartbeat_jobs.router)

# Dashboards
router.include_router(dashboards.router)

# Widget Data Refresh
router.include_router(widget_data.router)

# Dashboard Schedule Management
router.include_router(dashboard_schedule.router)

# Agent Sessions (Mesh)
router.include_router(agent_sessions.router)

# Feature Config
router.include_router(feature_config.router)

# Query Result Fetch (schema-only side-channel)
router.include_router(query_results.router)


# Upload
router.post("/upload", tags=["upload"])(upload.upload_file)

# Query
router.post("/query", tags=["query"])(query.query)
router.get("/search", tags=["query"])(query.search)

# Status
router.get("/status", tags=["status"])(health.get_status)
router.get("/info", tags=["status"])(health.app_info)

# Jobs
router.get("/jobs", tags=["jobs"])(jobs.list_all_jobs)
router.get("/jobs/{job_id}", tags=["jobs"])(jobs.get_job_status)
