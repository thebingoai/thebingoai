"""Add dashboard refresh schedule columns and run history table.

Revision ID: f9a0b1c2d3e4
Revises: e6f7a8b9c0d1
Create Date: 2026-03-07 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f9a0b1c2d3e4"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade():
    # Add schedule columns to dashboards table
    op.add_column("dashboards", sa.Column("schedule_type", sa.String(10), nullable=True))
    op.add_column("dashboards", sa.Column("schedule_value", sa.String(100), nullable=True))
    op.add_column("dashboards", sa.Column("cron_expression", sa.String(100), nullable=True))
    op.add_column("dashboards", sa.Column("schedule_active", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("dashboards", sa.Column("next_run_at", sa.DateTime(), nullable=True))
    op.add_column("dashboards", sa.Column("last_run_at", sa.DateTime(), nullable=True))

    op.create_index(
        "ix_dashboards_schedule_active_next_run",
        "dashboards",
        ["schedule_active", "next_run_at"],
    )

    # Create dashboard_refresh_runs table
    op.create_table(
        "dashboard_refresh_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("dashboard_id", sa.Integer(), sa.ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("widgets_total", sa.Integer(), nullable=True),
        sa.Column("widgets_succeeded", sa.Integer(), nullable=True),
        sa.Column("widgets_failed", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("widget_errors", sa.JSON(), nullable=True),
    )

    op.create_index(
        "ix_dashboard_refresh_runs_dashboard_id",
        "dashboard_refresh_runs",
        ["dashboard_id"],
    )


def downgrade():
    op.drop_index("ix_dashboard_refresh_runs_dashboard_id", table_name="dashboard_refresh_runs")
    op.drop_table("dashboard_refresh_runs")

    op.drop_index("ix_dashboards_schedule_active_next_run", table_name="dashboards")
    op.drop_column("dashboards", "last_run_at")
    op.drop_column("dashboards", "next_run_at")
    op.drop_column("dashboards", "schedule_active")
    op.drop_column("dashboards", "cron_expression")
    op.drop_column("dashboards", "schedule_value")
    op.drop_column("dashboards", "schedule_type")
