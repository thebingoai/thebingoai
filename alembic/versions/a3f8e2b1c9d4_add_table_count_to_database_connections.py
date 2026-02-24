"""add_table_count_to_database_connections

Revision ID: a3f8e2b1c9d4
Revises: 31531587d8a6
Create Date: 2026-02-24 10:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3f8e2b1c9d4'
down_revision = '31531587d8a6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('database_connections', sa.Column('table_count', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('database_connections', 'table_count')
