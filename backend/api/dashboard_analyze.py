"""One-shot dashboard analysis endpoint — runs the orchestrator and returns the result."""

import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database.session import get_db, SessionLocal
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.dashboard import Dashboard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboards", tags=["dashboard-analyze"])


@router.post("/{dashboard_id}/analyze")
async def analyze_dashboard(
    dashboard_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Run a one-shot orchestrator analysis of a dashboard and return the narrative result.

    Does not create a conversation thread or save any history.
    """
    # Verify the dashboard exists and belongs to this user
    dashboard = db.query(Dashboard).filter(
        Dashboard.id == dashboard_id,
        Dashboard.user_id == current_user.id,
    ).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    from backend.services.heartbeat_context import build_orchestrator_context
    from backend.agents import run_orchestrator

    prompt = (
        f"Use the analyze_dashboard tool on dashboard {dashboard_id}, then write a clear analysis report.\n\n"
        "Structure your report as follows:\n"
        "- Start with a 1-2 sentence executive summary of what this dashboard is about\n"
        "- Use **bold** section headings that are named after what the data actually shows "
        "(e.g. '**Revenue Performance**', '**Customer Trends**') — not generic labels like 'KPIs' or 'Widget 1'\n"
        "- For each section, state the current value or trend in plain language, then give one concrete insight or observation\n"
        "- End with a short **Key Takeaways** section (3 bullet points max) highlighting the most important findings\n\n"
        "Keep the tone concise and business-focused. Do not mention widget IDs, technical field names, or raw JSON."
    )

    try:
        ctx = await build_orchestrator_context(
            db=db,
            user=current_user,
            query=prompt,
            thread_id=str(uuid.uuid4()),
        )
    except Exception as e:
        logger.error("Failed to build orchestrator context for dashboard analysis: %s", e)
        raise HTTPException(status_code=500, detail="Failed to initialize analysis")

    try:
        result = await run_orchestrator(
            user_question=prompt,
            context=ctx.agent_context,
            history=[],
            custom_agents=ctx.custom_agents or None,
            db_session_factory=SessionLocal,
            memory_context=ctx.memory_context,
            user_skills=ctx.user_skills or None,
            user_memories_context=ctx.user_memories_context,
            soul_prompt=ctx.soul_prompt,
            skill_suggestions=ctx.skill_suggestions,
        )
    except Exception as e:
        logger.error("Orchestrator analysis failed for dashboard %s: %s", dashboard_id, e)
        raise HTTPException(status_code=500, detail="Analysis failed")

    return {
        "success": True,
        "dashboard_id": dashboard_id,
        "message": result.get("message", ""),
    }
