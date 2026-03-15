"""add_attachments_to_messages

Revision ID: b1c2d3e4f5a6
Revises: a4b5c6d7e8f9
Create Date: 2026-03-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b1c2d3e4f5a6'
down_revision = 'a4b5c6d7e8f9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('messages', sa.Column('attachments', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('messages', 'attachments')
