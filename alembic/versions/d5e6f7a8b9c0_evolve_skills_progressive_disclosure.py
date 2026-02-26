"""Evolve skills system: progressive disclosure, instruction skills, references, suggestions

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-02-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'd5e6f7a8b9c0'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add new columns to user_skills
    op.add_column('user_skills', sa.Column('skill_type', sa.String(20), nullable=True))
    op.add_column('user_skills', sa.Column('instructions', sa.Text(), nullable=True))
    op.add_column('user_skills', sa.Column('activation_hint', sa.Text(), nullable=True))
    op.add_column('user_skills', sa.Column('version', sa.Integer(), nullable=True))

    # 2. Backfill skill_type from existing data
    op.execute("""
        UPDATE user_skills
        SET skill_type = CASE
            WHEN code IS NOT NULL THEN 'code'
            WHEN prompt_template IS NOT NULL AND code IS NULL THEN 'prompt'
            ELSE 'prompt'
        END
    """)

    # 3. Backfill version = 1 for existing rows
    op.execute("UPDATE user_skills SET version = 1 WHERE version IS NULL")

    # 4. Make columns non-nullable now that backfill is done
    op.alter_column('user_skills', 'skill_type', nullable=False, server_default='code')
    op.alter_column('user_skills', 'version', nullable=False, server_default='1')

    # 5. Create skill_references table
    op.create_table(
        'skill_references',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('skill_id', sa.String(), sa.ForeignKey('user_skills.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_skill_references_skill_id', 'skill_references', ['skill_id'])

    # 6. Create skill_suggestions table
    op.create_table(
        'skill_suggestions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('suggested_name', sa.String(), nullable=False),
        sa.Column('suggested_description', sa.Text(), nullable=True),
        sa.Column('suggested_skill_type', sa.String(20), nullable=False, server_default='instruction'),
        sa.Column('suggested_instructions', sa.Text(), nullable=True),
        sa.Column('pattern_summary', sa.Text(), nullable=True),
        sa.Column('source_conversation_ids', JSONB(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_skill_suggestions_user_status', 'skill_suggestions', ['user_id', 'status'])


def downgrade():
    op.drop_index('ix_skill_suggestions_user_status', table_name='skill_suggestions')
    op.drop_table('skill_suggestions')
    op.drop_index('ix_skill_references_skill_id', table_name='skill_references')
    op.drop_table('skill_references')
    op.drop_column('user_skills', 'version')
    op.drop_column('user_skills', 'activation_hint')
    op.drop_column('user_skills', 'instructions')
    op.drop_column('user_skills', 'skill_type')
