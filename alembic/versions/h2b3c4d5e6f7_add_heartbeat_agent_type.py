"""Add agent_type column to heartbeat_jobs for agent mesh routing.

Revision ID: h2b3c4d5e6f7
Revises: g1a2b3c4d5e6
Create Date: 2026-03-18 18:30:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "h2b3c4d5e6f7"
down_revision = "g1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "heartbeat_jobs",
        sa.Column("agent_type", sa.String(50), nullable=True),
    )


def downgrade():
    op.drop_column("heartbeat_jobs", "agent_type")
