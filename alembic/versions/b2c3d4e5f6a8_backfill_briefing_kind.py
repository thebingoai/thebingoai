"""Backfill kind='briefing' for existing dashboard-analysis HeartbeatJob rows

Revision ID: b2c3d4e5f6a8
Revises: e472adcb3901
Create Date: 2026-05-08 11:00:00.000000
"""
from alembic import op

revision = "b2c3d4e5f6a8"
down_revision = "e472adcb3901"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE heartbeat_jobs
        SET kind = 'briefing'
        WHERE name LIKE 'Dashboard Analysis: %' AND kind = 'chat'
    """)


def downgrade():
    op.execute("""
        UPDATE heartbeat_jobs
        SET kind = 'chat'
        WHERE name LIKE 'Dashboard Analysis: %' AND kind = 'briefing'
    """)
