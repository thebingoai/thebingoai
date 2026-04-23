"""Add uuid column to database_connections

Revision ID: a1c2n3u4u5d6
Revises: z0b1c2d3e4f5
Create Date: 2026-04-23 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1c2n3u4u5d6'
down_revision = 'z0b1c2d3e4f5'
branch_labels = None
depends_on = None


def upgrade():
    # Add nullable with server-side default so Postgres backfills existing rows
    # atomically, then enforce NOT NULL and UNIQUE.
    op.add_column(
        "database_connections",
        sa.Column(
            "uuid",
            sa.String(length=36),
            nullable=True,
            server_default=sa.text("gen_random_uuid()::text"),
        ),
    )
    op.execute(
        "UPDATE database_connections SET uuid = gen_random_uuid()::text WHERE uuid IS NULL"
    )
    op.alter_column("database_connections", "uuid", nullable=False)
    op.create_unique_constraint(
        "uq_database_connections_uuid", "database_connections", ["uuid"]
    )


def downgrade():
    op.drop_constraint(
        "uq_database_connections_uuid", "database_connections", type_="unique"
    )
    op.drop_column("database_connections", "uuid")
