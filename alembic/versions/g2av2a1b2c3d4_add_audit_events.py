"""Phase G v2.a: add audit_events table + audit_retention_days on organizations.

Revision ID: g2av2a1b2c3d4
Revises: g1cv1c1b2c3d4
Create Date: 2026-05-08

`audit_events` is unpartitioned in v2.a. Monthly partitioning + the nightly
archive job land in v2.d alongside the Redis cache work.

`actor_user_id` is nullable: NULL means a system-context actor (background
task, scheduled run). Phase 0 ships system_context.py; the audit write
honors it directly.

`details` JSONB holds the sanitized event payload. The write helper strips
known-sensitive keys (password / token / token_hash / credentials_encrypted)
before persisting.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "g2av2a1b2c3d4"
down_revision = "g1cv1c1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("audit_retention_days", sa.Integer(), nullable=False, server_default="90"),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("actor_user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("org_id", sa.String(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=True),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_events_org_created", "audit_events", ["org_id", "created_at"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_actor", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_resource", "audit_events", ["resource_type", "resource_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_resource", table_name="audit_events")
    op.drop_index("ix_audit_events_actor", table_name="audit_events")
    op.drop_index("ix_audit_events_event_type", table_name="audit_events")
    op.drop_index("ix_audit_events_org_created", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_column("organizations", "audit_retention_days")
