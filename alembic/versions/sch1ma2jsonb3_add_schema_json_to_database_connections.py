"""add schema_json JSONB column to database_connections

Replaces DO Spaces-backed schema persistence. The `schema_json_path` column
becomes a marker (`"db:<id>"`) instead of a DO Spaces key; actual schema data
lives in the new `schema_json` JSONB column.

Revision ID: sch1ma2jsonb3
Revises: g8h9i0j1k2l3
Create Date: 2026-05-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "sch1ma2jsonb3"
down_revision = "g8h9i0j1k2l3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "database_connections",
        sa.Column("schema_json", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("database_connections", "schema_json")
