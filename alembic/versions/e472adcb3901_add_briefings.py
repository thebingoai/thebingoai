"""Add briefings table; add kind to conversations/heartbeat_jobs; add briefing_id to messages

Revision ID: e472adcb3901
Revises: 1b4144c01875
Create Date: 2026-05-08 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e472adcb3901"
down_revision = "1b4144c01875"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "briefings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("dashboard_id", sa.Integer(), sa.ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("heartbeat_job_id", sa.String(), sa.ForeignKey("heartbeat_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("date_range_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_range_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="generating"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "briefings_user_dashboard_idx",
        "briefings",
        ["user_id", "dashboard_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "briefings_inflight_idx",
        "briefings",
        ["user_id", "dashboard_id"],
        unique=True,
        postgresql_where=sa.text("status = 'generating'"),
    )

    op.add_column("conversations", sa.Column("kind", sa.String(20), nullable=False, server_default="chat"))
    op.create_index(
        "conversations_assistant_per_user_idx",
        "conversations",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'assistant'"),
    )

    op.add_column("heartbeat_jobs", sa.Column("kind", sa.String(20), nullable=False, server_default="chat"))

    op.add_column("messages", sa.Column("briefing_id", sa.BigInteger(), sa.ForeignKey("briefings.id", ondelete="SET NULL"), nullable=True))


def downgrade():
    op.drop_column("messages", "briefing_id")

    op.drop_column("heartbeat_jobs", "kind")

    op.drop_index("conversations_assistant_per_user_idx", table_name="conversations")
    op.drop_column("conversations", "kind")

    op.drop_index("briefings_inflight_idx", table_name="briefings")
    op.drop_index("briefings_user_dashboard_idx", table_name="briefings")
    op.drop_table("briefings")
