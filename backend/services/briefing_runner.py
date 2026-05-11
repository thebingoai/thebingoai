"""briefing_runner — generates a Briefing by invoking the orchestrator with the emit_briefing tool."""

import logging

from backend.database.session import SessionLocal
from backend.models.briefing import Briefing
from backend.models.dashboard import Dashboard
from backend.models.user import User
from backend.services.heartbeat_context import build_orchestrator_context
from backend.agents import run_orchestrator

logger = logging.getLogger(__name__)


_PROMPT = (
    "You are writing a structured briefing for dashboard {dashboard_id}.\n\n"
    "1. Use the analyze_dashboard tool to read the dashboard's KPIs and widgets.\n"
    "2. Reason about week-over-week (or period-over-period) change and what it means.\n"
    "3. Compose a coherent narrative: a sharp headline, a 1-2 sentence deck, up to 3 KPI tiles, "
    "1+ numbered sections (each may reference a relevant widget by id), and exactly 3 key takeaways.\n"
    "4. Call emit_briefing(payload=...) ONCE at the end with the structured payload. Do NOT write a prose response.\n\n"
    "{widget_catalog}\n"
    "The payload schema:\n"
    "{{\n"
    "  headline: str,\n"
    "  deck: str,\n"
    "  kpis: [{{label, value, delta_vs_prev?, delta_direction?}}, ...] (<=3),\n"
    "  sections: [{{heading, prose, widget_id?}}, ...] (>=1),\n"
    "  key_takeaways: [str, str, str]\n"
    "}}\n"
)


def _build_widget_catalog(widgets: list) -> str:
    """Produce a text catalog of widget ids and types for the orchestrator prompt."""
    if not widgets:
        return "This dashboard has no widgets."
    lines = ["Available widgets on this dashboard (use the exact widget_id in emit_briefing):"]
    for w in widgets:
        wid = w.get("id", "?")
        wtype = w.get("widget", {}).get("type", "?") if isinstance(w.get("widget"), dict) else "?"
        wtitle = (w.get("widget", {}) or {}).get("title", "") if isinstance(w.get("widget"), dict) else ""
        label = f"  - widget_id: {wid!r}, type: {wtype}"
        if wtitle:
            label += f', title: "{wtitle}"'
        lines.append(label)
    return "\n".join(lines)


async def run(briefing_id: int) -> None:
    """Generate a briefing. Updates the row with payload+status='ready' on success, status='failed' on error."""
    db = SessionLocal()
    briefing = None
    try:
        briefing = db.query(Briefing).filter(Briefing.id == briefing_id).first()
        if not briefing:
            logger.error("Briefing %s not found", briefing_id)
            return
        if briefing.status != "generating":
            logger.info("Briefing %s already in status=%s, skipping", briefing_id, briefing.status)
            return

        dashboard = db.query(Dashboard).filter(Dashboard.id == briefing.dashboard_id).first()
        user = db.query(User).filter(User.id == briefing.user_id).first()
        if not dashboard or not user:
            briefing.status = "failed"
            briefing.error = "Dashboard or user no longer exists"
            db.commit()
            return

        # Snapshot the dashboard date range (fields may not exist — getattr defends)
        briefing.date_range_from = getattr(dashboard, "date_range_from", None)
        briefing.date_range_to = getattr(dashboard, "date_range_to", None)
        db.commit()

        ctx = await build_orchestrator_context(
            db=db,
            user=user,
            query="",
            thread_id=None,
        )
        # Bind the briefing id so the orchestrator gets the emit_briefing tool
        ctx.agent_context.briefing_id = briefing_id

        # Build widget catalog so the orchestrator can reference real widget ids
        widget_catalog = _build_widget_catalog(dashboard.widgets or [])
        prompt = _PROMPT.format(
            dashboard_id=briefing.dashboard_id,
            widget_catalog=widget_catalog,
        )

        await run_orchestrator(
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
            profile=ctx.profile,
        )

        # Refresh the row — emit_briefing should have set status='ready'
        db.refresh(briefing)
        if briefing.status == "generating":
            # Orchestrator returned but never called emit_briefing — that's a failure
            briefing.status = "failed"
            briefing.error = "Orchestrator did not emit a briefing payload"
            db.commit()
            logger.warning("Briefing %s: orchestrator returned without emit_briefing", briefing_id)

    except Exception as e:
        logger.exception("Briefing %s generation raised: %s", briefing_id, e)
        if briefing is not None:
            briefing.status = "failed"
            briefing.error = str(e)
            try:
                db.commit()
            except Exception:
                db.rollback()
    finally:
        db.close()
