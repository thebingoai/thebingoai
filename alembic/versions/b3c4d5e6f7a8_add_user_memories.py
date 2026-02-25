"""Add user_memories table

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-02-25 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b3c4d5e6f7a8'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_memories',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_user_memories_user_id', 'user_memories', ['user_id'])


def downgrade():
    op.drop_index('ix_user_memories_user_id', table_name='user_memories')
    op.drop_table('user_memories')
