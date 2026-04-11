"""add input_tokens and output_tokens columns to credit_usage

Revision ID: u5n6o7p8q9r0
Revises: t4n5o6p7q8r9
Create Date: 2026-04-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "u5n6o7p8q9r0"
down_revision = "t4n5o6p7q8r9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("credit_usage", sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("credit_usage", sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("credit_usage", "output_tokens")
    op.drop_column("credit_usage", "input_tokens")
