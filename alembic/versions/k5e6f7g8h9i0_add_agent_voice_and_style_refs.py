"""add agent voice traits and soul style references

Revision ID: k5e6f7g8h9i0
Revises: 1b4144c01875, d1e2f3a4b5c6, d5e6f7a8b9c0, q1k2l3m4n5o6
Create Date: 2026-05-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'k5e6f7g8h9i0'
down_revision = ('1b4144c01875', 'd1e2f3a4b5c6', 'd5e6f7a8b9c0', 'q1k2l3m4n5o6')
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('agent_profiles', sa.Column('tone',             sa.Float(),              nullable=True))
    op.add_column('agent_profiles', sa.Column('style_traits',     postgresql.JSONB(),       nullable=True))
    op.add_column('agent_profiles', sa.Column('format_traits',    postgresql.JSONB(),       nullable=True))
    op.add_column('agent_profiles', sa.Column('style_references', postgresql.JSONB(),       nullable=True))


def downgrade() -> None:
    op.drop_column('agent_profiles', 'style_references')
    op.drop_column('agent_profiles', 'format_traits')
    op.drop_column('agent_profiles', 'style_traits')
    op.drop_column('agent_profiles', 'tone')
