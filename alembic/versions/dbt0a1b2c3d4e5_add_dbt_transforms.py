"""Add dbt_models and dbt_runs tables (Phase 4)

Revision ID: dbt0a1b2c3d4e5
Revises: h1i2j3k4l5m6
Create Date: 2026-05-06 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'dbt0a1b2c3d4e5'
down_revision = 'h1i2j3k4l5m6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'dbt_models',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('owner_scope_kind', sa.String(8), nullable=False),
        sa.Column('owner_scope_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('sql', sa.Text(), nullable=False),
        sa.Column('materialization', sa.String(16), nullable=False, server_default='table'),
        sa.Column('unique_key', sa.String(255), nullable=True),
        sa.Column('cron', sa.String(64), nullable=True),
        sa.Column('next_run_at', sa.DateTime(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('last_run_status', sa.String(16), nullable=True),
        sa.Column('last_profile_columns', postgresql.JSONB(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by_user_id', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint('owner_scope_kind', 'owner_scope_id', 'name', name='uq_dbt_model_scope_name'),
    )
    op.create_index('ix_dbt_model_enabled_next_run', 'dbt_models', ['enabled', 'next_run_at'])

    op.create_table(
        'dbt_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('owner_scope_kind', sa.String(8), nullable=False),
        sa.Column('owner_scope_id', sa.String(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(16), nullable=False, server_default='running'),
        sa.Column('models_run', postgresql.JSONB(), nullable=True),
        sa.Column('manifest_blob', sa.LargeBinary(), nullable=True),
        sa.Column('triggered_by', sa.String(16), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
    )
    op.create_index('ix_dbt_run_scope_started', 'dbt_runs', ['owner_scope_kind', 'owner_scope_id', 'started_at'])


def downgrade():
    op.drop_table('dbt_runs')
    op.drop_table('dbt_models')
