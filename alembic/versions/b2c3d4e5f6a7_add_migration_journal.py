"""Add migration_journal and widgets_pending_manual_rewrite tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-05 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "migration_journal",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("connection_id", sa.Integer(), sa.ForeignKey("database_connections.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("legacy_blob_path", sa.Text(), nullable=True),
        sa.Column("new_dataplane_table", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("widget_rewrites_applied", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("pre_migration_dataset_table_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_migration_journal_connection_id", "migration_journal", ["connection_id"])
    op.create_index("ix_migration_journal_status", "migration_journal", ["status"])

    op.create_table(
        "widgets_pending_manual_rewrite",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("widget_id", sa.String(36), nullable=False),
        sa.Column("connection_id", sa.Integer(), sa.ForeignKey("database_connections.id"), nullable=False),
        sa.Column("current_sql", sa.Text(), nullable=False),
        sa.Column("suggested_old_table", sa.String(255), nullable=True),
        sa.Column("suggested_new_table", sa.String(255), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_widgets_pending_manual_rewrite_connection_id", "widgets_pending_manual_rewrite", ["connection_id"])
    op.create_index("ix_widgets_pending_manual_rewrite_status", "widgets_pending_manual_rewrite", ["status"])


def downgrade():
    op.drop_table("widgets_pending_manual_rewrite")
    op.drop_table("migration_journal")
