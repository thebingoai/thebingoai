"""Celery tasks for heartbeat job scheduling and execution."""

import asyncio
import logging
from datetime import datetime

from celery import shared_task
from backend.database.session import SessionLocal
from backend.models.heartbeat_job import HeartbeatJob
from backend.models.heartbeat_job_run import HeartbeatJobRun, HeartbeatRunStatus
from backend.models.user import User
from backend.tasks._helpers import record_run_failure

logger = logging.getLogger(__name__)


@shared_task(name="dispatch_heartbeat_jobs")
def dispatch_heartbeat_jobs():
    """
    Dispatcher task that runs every 60 seconds via Celery Beat.

    Queries all active jobs whose next_run_at is due and dispatches
    an execute_heartbeat_job task for each, then advances next_run_at.
    """
    from backend.tasks.cron_dispatcher import dispatch_due_rows

    db = SessionLocal()
    now = datetime.utcnow()

    def _dispatch_heartbeat_row(job, _now=now):
        if getattr(job, "kind", "chat") == "briefing":
            execute_heartbeat_briefing.delay(job.id)
        elif job.agent_type and job.agent_type != "orchestrator":
            execute_agent_heartbeat_job.delay(job.id)
        else:
            execute_heartbeat_job.delay(job.id)
        job.last_run_at = _now

    try:
        count = dispatch_due_rows(
            db,
            model_cls=HeartbeatJob,
            enabled_field="is_active",
            cron_field="cron_expression",
            next_run_field="next_run_at",
            dispatch_fn=_dispatch_heartbeat_row,
            now=now,
        )
        if count:
            logger.info("Dispatched %d due heartbeat job(s)", count)
        db.commit()
    except Exception as e:
        logger.error("dispatch_heartbeat_jobs failed: %s", e)
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
            status=HeartbeatRunStatus.RUNNING.value,
            started_at=started_at,
            prompt=job.prompt,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        logger.info(f"Executing heartbeat job {job_id} (run {run.id})")

        with record_run_failure(
            db,
            run,
            HeartbeatRunStatus.FAILED.value,
            started_at,
            logger=logger,
            task_label=f"Heartbeat job {job_id}",
        ):
            # --- Credit tracking (bingo-credits plugin) ---
            _credit_mgr = None
            try:
                from backend.plugins.loader import get_loaded_plugins
                if "bingo-admin" in get_loaded_plugins():
                    from bingo_admin.credit_context import CreditContextManager
                else:
                    from backend.services.token_tracking_service import CreditContextManager
                _credit_mgr = CreditContextManager(
                    db=db,
                    user_id=job.user_id,
                    title=f"Heartbeat: {job.prompt[:60]}",
                    provider_name=None,
                    conversation_id=None,
                    block_on_insufficient=False,
                )
            except Exception as _credit_err:
                logger.warning("Credit context setup failed for heartbeat: %s", _credit_err)
                _credit_mgr = None

            # Sync context manager propagates ContextVar into asyncio.run()
            from contextlib import nullcontext
            with (_credit_mgr if _credit_mgr is not None else nullcontext()):
                response = asyncio.run(_run_orchestrator_for_job(job, user))

            completed_at = datetime.utcnow()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            run.status = HeartbeatRunStatus.COMPLETED.value
            run.response = response
            run.completed_at = completed_at
            run.duration_ms = duration_ms
            db.commit()

            logger.info(f"Heartbeat job {job_id} run {run.id} completed in {duration_ms}ms")

            # Deliver result to user's permanent conversation
            _deliver_heartbeat_result(db, job=job, run_id=run.id, user_id=job.user_id, response=response)
    finally:
        db.close()


def _deliver_heartbeat_result(db, *, job: HeartbeatJob, run_id: str, user_id: str, response: str) -> None:
    """
    Save the heartbeat response to the user's permanent conversation and
    publish a WebSocket notification via Redis Pub/Sub.

    This is a synchronous helper (Celery workers are sync).
    """
    from backend.services.conversation_service import ConversationService
    from backend.models.message import Message
    from backend.services.ws_connection_manager import ConnectionManager

    try:
        perm_conv = ConversationService.get_or_create_permanent_conversation(db, user_id)

        msg = Message(
            conversation_id=perm_conv.id,
            role="assistant",
            content=response,
            source="heartbeat",
            heartbeat_job_id=job.id,
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)

        payload = {
            "type": "heartbeat.message",
            "thread_id": perm_conv.thread_id,
            "message": {
                "id": msg.id,
                "role": "assistant",
                "content": response,
                "source": "heartbeat",
                "job_name": job.name,
                "job_id": job.id,
                "timestamp": msg.timestamp.isoformat(),
            },
        }
        ConnectionManager.publish_to_user_sync(user_id, payload)
        logger.info(f"Heartbeat result delivered to permanent conv for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to deliver heartbeat result to user {user_id}: {e}")


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

    from backend.agents.profile_llm import resolve_published_llm
    user_provider, profile_temperature, profile_max_tokens = resolve_published_llm(ctx.profile)
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
        soul_prompt=ctx.soul_prompt,
        skill_suggestions=ctx.skill_suggestions,
        profile=ctx.profile,
        llm_provider=user_provider,
        temperature=profile_temperature,
        max_tokens=profile_max_tokens,
    )

    return result.get("message", "")


@shared_task(name="execute_agent_heartbeat_job", time_limit=300)
def execute_agent_heartbeat_job(job_id: str):
    """
    Execute a heartbeat job routed to a specific agent type (not the orchestrator).

    Creates a session for the agent and runs it via AgentRuntime.
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

        run = HeartbeatJobRun(
            job_id=job_id,
            status=HeartbeatRunStatus.RUNNING.value,
            started_at=started_at,
            prompt=job.prompt,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        logger.info(f"Executing agent heartbeat job {job_id} (type={job.agent_type}, run={run.id})")

        with record_run_failure(
            db,
            run,
            HeartbeatRunStatus.FAILED.value,
            started_at,
            logger=logger,
            task_label=f"Agent heartbeat job {job_id}",
        ):
            # --- Credit tracking (bingo-credits plugin) ---
            _credit_mgr = None
            try:
                from backend.plugins.loader import get_loaded_plugins
                if "bingo-admin" in get_loaded_plugins():
                    from bingo_admin.credit_context import CreditContextManager
                else:
                    from backend.services.token_tracking_service import CreditContextManager
                _credit_mgr = CreditContextManager(
                    db=db,
                    user_id=job.user_id,
                    title=f"Heartbeat: {job.prompt[:60]}",
                    provider_name=None,
                    conversation_id=None,
                    block_on_insufficient=False,
                )
            except Exception as _credit_err:
                logger.warning("Credit context setup failed for heartbeat: %s", _credit_err)
                _credit_mgr = None

            from contextlib import nullcontext
            with (_credit_mgr if _credit_mgr is not None else nullcontext()):
                response = asyncio.run(
                    _run_agent_for_job(job, user)
                )

            completed_at = datetime.utcnow()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            run.status = HeartbeatRunStatus.COMPLETED.value
            run.response = response
            run.completed_at = completed_at
            run.duration_ms = duration_ms
            db.commit()

            _deliver_heartbeat_result(db, job=job, run_id=run.id, user_id=job.user_id, response=response)
    finally:
        db.close()


async def _run_agent_for_job(job: HeartbeatJob, user: User) -> str:
    """
    Run a specific agent type for a heartbeat job via AgentRuntime.
    """
    import uuid
    from backend.agents.context import AgentContext
    from backend.agents.runtime import AgentRuntime
    from backend.services.agent_registry import AgentRegistry
    from backend.services.agent_message_bus import AgentMessageBus
    from backend.models.database_connection import DatabaseConnection

    db = SessionLocal()
    try:
        # Get user's connections
        conn_ids = [
            row.id for row in db.query(DatabaseConnection.id)
            .filter(DatabaseConnection.user_id == user.id)
            .all()
        ]

        session_id = str(uuid.uuid4())
        context = AgentContext(
            user_id=user.id,
            available_connections=conn_ids,
            thread_id=str(uuid.uuid4()),
            session_id=session_id,
        )

        registry = AgentRegistry()
        message_bus = AgentMessageBus(db_session=db, redis_client=registry.redis)

        from backend.tasks.agent_tasks import _build_agent_config
        tools, prompt = _build_agent_config(job.agent_type, context, db)

        runtime = AgentRuntime(
            session_id=session_id,
            agent_type=job.agent_type,
            user_id=user.id,
            context=context,
            registry=registry,
            message_bus=message_bus,
        )

        result = await runtime.execute(job.prompt, tools, prompt)
        return result.get("message", "")

    finally:
        db.close()


@shared_task(name="execute_heartbeat_briefing", time_limit=60)
def execute_heartbeat_briefing(job_id: str):
    """For a briefing-kind HeartbeatJob: create a Briefing row and dispatch generate_briefing."""
    from backend.models.briefing import Briefing
    from backend.tasks.briefing_tasks import generate_briefing
    import re

    db = SessionLocal()
    try:
        job = db.query(HeartbeatJob).filter(HeartbeatJob.id == job_id).first()
        if not job:
            logger.error("execute_heartbeat_briefing: job %s missing", job_id)
            return

        # Extract dashboard_id from prompt: "analyze dashboard {id} ..."
        m = re.search(r"dashboard\s+(\d+)", job.prompt or "")
        if not m:
            logger.error("execute_heartbeat_briefing: cannot find dashboard id in prompt %r", job.prompt)
            return
        dashboard_id = int(m.group(1))

        # Idempotency: skip if there's already an in-flight briefing for this job within the last minute
        from datetime import timedelta
        recent = (
            db.query(Briefing)
            .filter(
                Briefing.heartbeat_job_id == job.id,
                Briefing.created_at >= datetime.utcnow() - timedelta(minutes=1),
            )
            .first()
        )
        if recent:
            logger.info("execute_heartbeat_briefing: recent run exists (briefing %s), skipping", recent.id)
            return

        briefing = Briefing(
            user_id=job.user_id,
            dashboard_id=dashboard_id,
            source="scheduled",
            heartbeat_job_id=job.id,
            status="generating",
        )
        db.add(briefing)
        db.commit()
        db.refresh(briefing)

        generate_briefing.delay(briefing.id)
    finally:
        db.close()
