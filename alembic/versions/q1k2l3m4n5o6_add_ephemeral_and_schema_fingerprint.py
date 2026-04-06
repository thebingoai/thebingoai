"""add_ephemeral_and_schema_fingerprint

Revision ID: q1k2l3m4n5o6
Revises: p0j1k2l3m4n5
Create Date: 2026-04-04 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'q1k2l3m4n5o6'
down_revision = 'p0j1k2l3m4n5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('database_connections', sa.Column('is_ephemeral', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('database_connections', sa.Column('schema_fingerprint', sa.String(64), nullable=True))


def downgrade():
    op.drop_column('database_connections', 'schema_fingerprint')
    op.drop_column('database_connections', 'is_ephemeral')
