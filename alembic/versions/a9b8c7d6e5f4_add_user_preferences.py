"""Add preferences column to users table

Revision ID: a9b8c7d6e5f4
Revises: s3e3d4f5a6b7
Create Date: 2026-02-25 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a9b8c7d6e5f4'
down_revision = 's3e3d4f5a6b7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('preferences', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('users', 'preferences')
