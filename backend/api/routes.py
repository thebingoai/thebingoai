from fastapi import APIRouter
from backend.api import upload, query, chat, health, jobs, auth, connections

router = APIRouter()

# Authentication
router.include_router(auth.router)

# Database Connections
router.include_router(connections.router)

# Upload
router.post("/upload", tags=["upload"])(upload.upload_file)

# Query
router.post("/query", tags=["query"])(query.query)
router.get("/search", tags=["query"])(query.search)

# Chat/RAG
router.post("/ask", tags=["chat"], response_model=None)(chat.ask)
router.get("/providers", tags=["chat"])(chat.list_providers)

# Conversation Memory (LangGraph)
router.delete("/conversation/{thread_id}", tags=["chat"])(chat.delete_history)

# Status
router.get("/status", tags=["status"])(health.get_status)

# Jobs
router.get("/jobs", tags=["jobs"])(jobs.list_all_jobs)
router.get("/jobs/{job_id}", tags=["jobs"])(jobs.get_job_status)
