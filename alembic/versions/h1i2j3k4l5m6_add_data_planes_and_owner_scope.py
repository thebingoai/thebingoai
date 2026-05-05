"""Add data_planes table and owner_scope columns on database_connections.

Revision ID: h1i2j3k4l5m6
Revises: g0h1i2j3k4l5
Create Date: 2026-05-05 18:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "h1i2j3k4l5m6"
down_revision = "g0h1i2j3k4l5"
branch_labels = None
depends_on = None


def upgrade():
    # ── data_planes table ─────────────────────────────────────────────────
    op.create_table(
        "data_planes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_scope_kind", sa.String(8), nullable=False),
        sa.Column("owner_scope_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("credentials_encrypted", sa.String(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # At most one default plane per scope
    op.create_index(
        "uq_data_planes_default_per_scope",
        "data_planes",
        ["owner_scope_kind", "owner_scope_id"],
        unique=False,
        postgresql_where=sa.text("is_default = true"),
    )
    op.create_index(
        "ix_data_planes_scope",
        "data_planes",
        ["owner_scope_kind", "owner_scope_id"],
    )

    # ── owner_scope columns on database_connections ───────────────────────
    # Add nullable first so existing rows don't violate the constraint.
    op.add_column(
        "database_connections",
        sa.Column("owner_scope_kind", sa.String(8), nullable=True),
    )
    op.add_column(
        "database_connections",
        sa.Column("owner_scope_id", sa.String(), nullable=True),
    )

    # Backfill: org_id wins; fall back to user_id
    op.execute(
        """
        UPDATE database_connections
        SET
            owner_scope_kind = CASE
                WHEN org_id IS NOT NULL THEN 'org'
                ELSE 'user'
            END,
            owner_scope_id = COALESCE(org_id, user_id)
        """
    )

    # Tighten to NOT NULL after backfill
    op.alter_column("database_connections", "owner_scope_kind", nullable=False)
    op.alter_column(
        "database_connections",
        "owner_scope_id",
        nullable=False,
        server_default="''",
    )


def downgrade():
    op.drop_column("database_connections", "owner_scope_id")
    op.drop_column("database_connections", "owner_scope_kind")
    op.drop_index("ix_data_planes_scope", table_name="data_planes")
    op.drop_index("uq_data_planes_default_per_scope", table_name="data_planes")
    op.drop_table("data_planes")
