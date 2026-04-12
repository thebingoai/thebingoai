"""add user_roles table

Revision ID: w7p8q9r0s1t2
Revises: v6o7p8q9r0s1
Create Date: 2026-04-12

"""
from alembic import op
import sqlalchemy as sa

revision = 'w7p8q9r0s1t2'
down_revision = 'v6o7p8q9r0s1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_roles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, server_default='user'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )


def downgrade() -> None:
    op.drop_table('user_roles')
