"""Add pipelines, pipeline_runs, dlt_pipeline_states tables

Revision ID: a1b2c3d4e5f6
Revises: z0b1c2d3e4f5
Create Date: 2026-05-05 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a1b2c3d4e5f6'
down_revision = 'z0b1c2d3e4f5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pipelines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_scope_kind", sa.String(8), nullable=False),
        sa.Column("owner_scope_id", sa.String(), nullable=False),
        sa.Column("source_connection_id", sa.Integer(), sa.ForeignKey("database_connections.id"), nullable=False),
        sa.Column("data_plane_id", sa.String(36), sa.ForeignKey("data_planes.id"), nullable=True),
        sa.Column("target_table", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("cron", sa.String(64), nullable=True),
        sa.Column("mode", sa.String(16), nullable=False, server_default="full"),
        sa.Column("incremental_key", sa.String(255), nullable=True),
        sa.Column("extraction_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("pipeline_fingerprint", sa.String(128), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_status", sa.String(16), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("owner_scope_kind", "owner_scope_id", "pipeline_fingerprint",
                            name="uq_pipeline_scope_fingerprint"),
    )
    op.create_index("ix_pipeline_enabled_next_run_at", "pipelines", ["enabled", "next_run_at"])

    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pipeline_id", sa.String(36), sa.ForeignKey("pipelines.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("rows_written", sa.Integer(), nullable=True),
        sa.Column("bytes_written", sa.BigInteger(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(16), nullable=False),
        sa.Column("triggered_by_user_id", sa.String(), nullable=True),
    )
    op.create_index("ix_pipeline_run_pipeline_started", "pipeline_runs",
                    ["pipeline_id", "started_at"])

    op.create_table(
        "dlt_pipeline_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_scope_kind", sa.String(8), nullable=False),
        sa.Column("owner_scope_id", sa.String(), nullable=False),
        sa.Column("pipeline_id", sa.String(36), sa.ForeignKey("pipelines.id"), nullable=False),
        sa.Column("state_blob", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("pipeline_id", name="uq_dlt_state_pipeline"),
    )


def downgrade():
    op.drop_table("dlt_pipeline_states")
    op.drop_table("pipeline_runs")
    op.drop_index("ix_pipeline_enabled_next_run_at", table_name="pipelines")
    op.drop_table("pipelines")
