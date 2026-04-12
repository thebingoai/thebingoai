"""change credits_used to integer

Revision ID: v6o7p8q9r0s1
Revises: u5n6o7p8q9r0
Create Date: 2026-04-10

"""
from alembic import op
import sqlalchemy as sa

revision = 'v6o7p8q9r0s1'
down_revision = 'u5n6o7p8q9r0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'credit_usage', 'credits_used',
        existing_type=sa.Numeric(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using='credits_used::integer',
    )


def downgrade() -> None:
    op.alter_column(
        'credit_usage', 'credits_used',
        existing_type=sa.Integer(),
        type_=sa.Numeric(),
        existing_nullable=False,
    )
