"""Add is_autonomous and schedule columns to custom_agents.

Revision ID: i3c4d5e6f7g8
Revises: h2b3c4d5e6f7
Create Date: 2026-03-18 18:45:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "i3c4d5e6f7g8"
down_revision = "h2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "custom_agents",
        sa.Column("is_autonomous", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "custom_agents",
        sa.Column("schedule", sa.String(100), nullable=True),
    )


def downgrade():
    op.drop_column("custom_agents", "schedule")
    op.drop_column("custom_agents", "is_autonomous")
