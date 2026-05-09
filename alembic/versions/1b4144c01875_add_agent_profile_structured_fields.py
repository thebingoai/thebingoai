"""Add structured fields to agent_profiles for Agent Identity settings

Revision ID: 1b4144c01875
Revises: a1c2n3u4u5d6
Create Date: 2026-05-06 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '1b4144c01875'
down_revision = 'a1c2n3u4u5d6'
branch_labels = None
depends_on = None

_NEW_COLS = [
    ('display_name',      sa.String(100)),
    ('pronouns',          sa.String(50)),
    ('tagline',           sa.String(200)),
    ('avatar_url',        sa.String(500)),
    ('default_model',     sa.String(100)),
    ('temperature',       sa.Float()),
    ('max_output_tokens', sa.Integer()),
    ('user_profile',      postgresql.JSONB()),
    ('user_narrative',    sa.Text()),
    ('vocabulary',        postgresql.JSONB()),
    ('sensitivities',     postgresql.JSONB()),
    ('published_at',      sa.DateTime()),
    ('published_snapshot', postgresql.JSONB()),
    ('published_version', sa.Integer()),
]

def upgrade():
    for col_name, col_type in _NEW_COLS:
        op.add_column('agent_profiles', sa.Column(col_name, col_type, nullable=True))

def downgrade():
    for col_name, _ in reversed(_NEW_COLS):
        op.drop_column('agent_profiles', col_name)
