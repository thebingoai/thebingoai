"""Celery tasks for heartbeat job scheduling and execution."""

import asyncio
import logging
from datetime import datetime

from celery import shared_task
from backend.database.session import SessionLocal
from backend.models.heartbeat_job import HeartbeatJob
from backend.models.heartbeat_job_run import HeartbeatJobRun
from backend.models.user import User

logger = logging.getLogger(__name__)


@shared_task(name="dispatch_heartbeat_jobs")
def dispatch_heartbeat_jobs():
    """
    Dispatcher task that runs every 60 seconds via Celery Beat.

    Queries all active jobs whose next_run_at is due and dispatches
    an execute_heartbeat_job task for each, then advances next_run_at.
    """
    from croniter import croniter

    db = SessionLocal()
    now = datetime.utcnow()

    try:
        due_jobs = (
            db.query(HeartbeatJob)
            .filter(
                HeartbeatJob.is_active == True,
                HeartbeatJob.next_run_at <= now,
            )
            .all()
        )

        if not due_jobs:
            return

        logger.info(f"Dispatching {len(due_jobs)} due heartbeat job(s)")

        for job in due_jobs:
            try:
                execute_heartbeat_job.delay(job.id)
                # Advance next_run_at
                job.next_run_at = croniter(job.cron_expression, now).get_next(datetime)
                job.last_run_at = now
            except Exception as dispatch_err:
                logger.error(f"Failed to dispatch job {job.id}: {dispatch_err}")

        db.commit()

    except Exception as e:
        logger.error(f"dispatch_heartbeat_jobs failed: {e}")
        db.rollback()
    finally:
        db.close()


@shared_task(name="execute_heartbeat_job", time_limit=300)
def execute_heartbeat_job(job_id: str):
    """
    Execute a single heartbeat job: invoke the orchestrator and record the run.

    Args:
        job_id: The ID of the HeartbeatJob to execute.
    """
    db = SessionLocal()
    run = None
    started_at = datetime.utcnow()

    try:
        job = db.query(HeartbeatJob).filter(HeartbeatJob.id == job_id).first()
        if not job:
            logger.warning(f"Heartbeat job {job_id} not found")
            return

        user = db.query(User).filter(User.id == job.user_id).first()
        if not user:
            logger.warning(f"User {job.user_id} not found for job {job_id}")
            return

        # Create a run record
        run = HeartbeatJobRun(
            job_id=job_id,
            status="running",
            started_at=started_at,
            prompt=job.prompt,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        logger.info(f"Executing heartbeat job {job_id} (run {run.id})")

        # Run the orchestrator synchronously (Celery workers are sync)
        response = asyncio.run(_run_orchestrator_for_job(job, user))

        completed_at = datetime.utcnow()
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)

        run.status = "completed"
        run.response = response
        run.completed_at = completed_at
        run.duration_ms = duration_ms
        db.commit()

        logger.info(f"Heartbeat job {job_id} run {run.id} completed in {duration_ms}ms")

    except Exception as e:
        logger.error(f"Heartbeat job {job_id} failed: {e}")
        if run is not None:
            try:
                completed_at = datetime.utcnow()
                run.status = "failed"
                run.error = str(e)
                run.completed_at = completed_at
                run.duration_ms = int((completed_at - started_at).total_seconds() * 1000)
                db.commit()
            except Exception:
                db.rollback()
    finally:
        db.close()


async def _run_orchestrator_for_job(job: HeartbeatJob, user: User) -> str:
    """
    Async inner function that builds context and invokes the orchestrator.

    Returns the orchestrator's response as a string.
    """
    import uuid
    from backend.agents import run_orchestrator
    from backend.services.heartbeat_context import build_orchestrator_context
    from backend.database.session import SessionLocal

    db = SessionLocal()
    try:
        ctx = await build_orchestrator_context(
            db=db,
            user=user,
            query=job.prompt,
            connection_ids=None,  # Use all user connections
            thread_id=str(uuid.uuid4()),  # Fresh thread per run
        )
    finally:
        db.close()

    db_factory = SessionLocal
    result = await run_orchestrator(
        user_question=job.prompt,
        context=ctx.agent_context,
        history=[],
        custom_agents=ctx.custom_agents or None,
        db_session_factory=db_factory,
        memory_context=ctx.memory_context,
        user_skills=ctx.user_skills or None,
        user_memories_context=ctx.user_memories_context,
    )

    return result.get("message", "")
