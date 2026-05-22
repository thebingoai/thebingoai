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


def _col_exists(conn, table, column):
    return conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns"
            " WHERE table_name=:t AND column_name=:c"
        ),
        {"t": table, "c": column},
    ).fetchone() is not None


def _table_exists(conn, table):
    return conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name=:t"
        ),
        {"t": table},
    ).fetchone() is not None


def _index_exists(conn, index):
    return conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE indexname=:i"
        ),
        {"i": index},
    ).fetchone() is not None


def upgrade():
    conn = op.get_bind()

    # ── data_planes table ─────────────────────────────────────────────────
    if not _table_exists(conn, "data_planes"):
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

    if not _index_exists(conn, "uq_data_planes_default_per_scope"):
        op.create_index(
            "uq_data_planes_default_per_scope",
            "data_planes",
            ["owner_scope_kind", "owner_scope_id"],
            unique=False,
            postgresql_where=sa.text("is_default = true"),
        )

    if not _index_exists(conn, "ix_data_planes_scope"):
        op.create_index(
            "ix_data_planes_scope",
            "data_planes",
            ["owner_scope_kind", "owner_scope_id"],
        )

    # ── owner_scope columns on database_connections ───────────────────────
    added_kind = False
    if not _col_exists(conn, "database_connections", "owner_scope_kind"):
        op.add_column(
            "database_connections",
            sa.Column("owner_scope_kind", sa.String(8), nullable=True),
        )
        added_kind = True

    added_id = False
    if not _col_exists(conn, "database_connections", "owner_scope_id"):
        op.add_column(
            "database_connections",
            sa.Column("owner_scope_id", sa.String(), nullable=True),
        )
        added_id = True

    if added_kind or added_id:
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
            WHERE owner_scope_kind IS NULL OR owner_scope_id IS NULL
            """
        )

    if added_kind:
        op.alter_column("database_connections", "owner_scope_kind", nullable=False)
    if added_id:
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
