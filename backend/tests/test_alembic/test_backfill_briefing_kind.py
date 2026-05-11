"""Verifies the b2c3d4e5f6a7 backfill migration flips Dashboard-Analysis HeartbeatJob rows to kind='briefing'."""
from sqlalchemy import text
from alembic.config import Config
from alembic import command
import pytest


def test_backfill_promotes_dashboard_analysis_jobs():
    cfg = Config("alembic.ini")

    # Downgrade to just after the main briefing migration (before this backfill)
    command.downgrade(cfg, "e472adcb3901")

    from backend.database.session import SessionLocal
    db = SessionLocal()
    try:
        # Pick a real user id to satisfy the FK constraint
        users = db.execute(text("SELECT id FROM users LIMIT 1")).fetchall()
        assert users, "Need at least one user in the database for the test"
        user_id = users[0][0]

        # Ensure test data
        db.execute(text("DELETE FROM heartbeat_jobs WHERE id IN ('job-bf-1','job-bf-2','job-bf-3')"))
        db.execute(text("""
            INSERT INTO heartbeat_jobs (id, user_id, name, prompt, schedule_type, schedule_value,
                                        cron_expression, is_active, kind)
            VALUES
              (:id1, :uid, 'Dashboard Analysis: Northwind', 'analyze dashboard 1', 'preset', '1d', '0 9 * * *', true, 'chat'),
              (:id2, :uid, 'Dashboard Analysis: Acme', 'analyze dashboard 2', 'preset', '1d', '0 9 * * *', true, 'chat'),
              (:id3, :uid, 'Other Job', 'do something', 'preset', '1d', '0 9 * * *', true, 'chat')
        """), {"id1": "job-bf-1", "id2": "job-bf-2", "id3": "job-bf-3", "uid": user_id})
        db.commit()
    finally:
        db.close()

    # Run the backfill
    command.upgrade(cfg, "b2c3d4e5f6a7")

    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT id, kind FROM heartbeat_jobs WHERE id IN ('job-bf-1','job-bf-2','job-bf-3') ORDER BY id"
        )).fetchall()
    finally:
        db.close()

    by_id = {r[0]: r[1] for r in rows}
    assert by_id["job-bf-1"] == "briefing"
    assert by_id["job-bf-2"] == "briefing"
    assert by_id["job-bf-3"] == "chat"  # unaffected

    # Restore to head
    command.upgrade(cfg, "head")
