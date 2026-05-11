"""schedule_briefing — orchestrator tool to create or update a recurring briefing schedule."""

import json
import logging
from typing import Callable
from langchain_core.tools import tool

from backend.agents.context import AgentContext

logger = logging.getLogger(__name__)


def build_schedule_briefing_tool(context: AgentContext, db_session_factory: Callable) -> list:
    """Return the schedule_briefing tool bound to the current user context."""

    @tool
    async def schedule_briefing(dashboard_name: str, cron: str) -> str:
        """Schedule a recurring AI briefing for a dashboard using a cron expression.

        Creates (or updates) a HeartbeatJob that fires on the given cron schedule,
        runs the briefing orchestrator against the dashboard, and delivers the result
        as a BriefingCard in this chat.

        Args:
            dashboard_name: Partial or full name of the dashboard to brief.
            cron: Standard 5-field cron expression, e.g. "0 9 * * 1" for every Monday at 9 AM.
                  Server timezone is UTC.

        Returns:
            JSON with job_id, cron_expression, next_run_at, and dashboard_id on success.
        """
        from backend.models.dashboard import Dashboard
        from backend.schemas.heartbeat import resolve_cron_expression
        from backend.models.heartbeat_job import HeartbeatJob
        from datetime import datetime
        from croniter import croniter

        db = db_session_factory()
        try:
            # Resolve dashboard by partial name match
            dashboards = (
                db.query(Dashboard)
                .filter(
                    Dashboard.user_id == context.user_id,
                    Dashboard.title.ilike(f"%{dashboard_name}%"),
                )
                .all()
            )
            if not dashboards:
                return json.dumps({"success": False, "message": f"No dashboard found matching '{dashboard_name}'"})
            if len(dashboards) > 1:
                names = ", ".join(f'"{d.title}"' for d in dashboards)
                return json.dumps({"success": False, "message": f"Multiple dashboards match — be more specific: {names}"})

            dashboard = dashboards[0]

            # Validate cron expression
            try:
                resolved = resolve_cron_expression("cron", cron)
            except ValueError as e:
                return json.dumps({"success": False, "message": f"Invalid cron: {e}"})

            now = datetime.utcnow()
            next_run = croniter(resolved, now).get_next(datetime)
            job_name = f"Dashboard Analysis: {dashboard.title}"

            existing = (
                db.query(HeartbeatJob)
                .filter(
                    HeartbeatJob.user_id == context.user_id,
                    HeartbeatJob.name == job_name,
                )
                .first()
            )

            if existing:
                existing.schedule_type = "cron"
                existing.schedule_value = cron
                existing.cron_expression = resolved
                existing.next_run_at = next_run
                existing.is_active = True
                existing.kind = "briefing"
                job = existing
            else:
                job = HeartbeatJob(
                    user_id=context.user_id,
                    name=job_name,
                    prompt=f"analyze dashboard {dashboard.id}",
                    schedule_type="cron",
                    schedule_value=cron,
                    cron_expression=resolved,
                    agent_type=None,
                    kind="briefing",
                    is_active=True,
                    next_run_at=next_run,
                )
                db.add(job)

            db.commit()
            db.refresh(job)

            return json.dumps({
                "success": True,
                "job_id": job.id,
                "dashboard_id": dashboard.id,
                "dashboard_name": dashboard.title,
                "cron_expression": resolved,
                "next_run_at": next_run.isoformat() + "Z",
            })

        except Exception as e:
            logger.exception("schedule_briefing tool failed: %s", e)
            db.rollback()
            return json.dumps({"success": False, "message": str(e)})
        finally:
            db.close()

    return [schedule_briefing]
