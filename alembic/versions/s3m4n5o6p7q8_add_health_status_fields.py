"""add health_status and health_checked_at to database_connections

Revision ID: s3m4n5o6p7q8
Revises: r2l3m4n5o6p7
Create Date: 2026-04-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "s3m4n5o6p7q8"
down_revision = "r2l3m4n5o6p7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("database_connections", sa.Column("health_status", sa.String(), nullable=True))
    op.add_column("database_connections", sa.Column("health_checked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("database_connections", "health_checked_at")
    op.drop_column("database_connections", "health_status")
