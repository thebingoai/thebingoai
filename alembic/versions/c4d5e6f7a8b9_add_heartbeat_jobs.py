"""Add heartbeat_jobs and heartbeat_job_runs tables

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-02-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'c4d5e6f7a8b9'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'heartbeat_jobs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('schedule_type', sa.String(10), nullable=False),
        sa.Column('schedule_value', sa.String(100), nullable=False),
        sa.Column('cron_expression', sa.String(100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('next_run_at', sa.DateTime(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_heartbeat_jobs_user_id', 'heartbeat_jobs', ['user_id'])
    op.create_index('ix_heartbeat_jobs_active_next_run', 'heartbeat_jobs', ['is_active', 'next_run_at'])

    op.create_table(
        'heartbeat_job_runs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('job_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='running'),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=True),
        sa.Column('response', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['heartbeat_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_heartbeat_job_runs_job_id', 'heartbeat_job_runs', ['job_id'])


def downgrade():
    op.drop_index('ix_heartbeat_job_runs_job_id', table_name='heartbeat_job_runs')
    op.drop_table('heartbeat_job_runs')
    op.drop_index('ix_heartbeat_jobs_active_next_run', table_name='heartbeat_jobs')
    op.drop_index('ix_heartbeat_jobs_user_id', table_name='heartbeat_jobs')
    op.drop_table('heartbeat_jobs')
