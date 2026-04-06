"""add skill suggestion evaluation fields

Revision ID: r2l3m4n5o6p7
Revises: q1k2l3m4n5o6
Create Date: 2026-04-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "r2l3m4n5o6p7"
down_revision = "q1k2l3m4n5o6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("skill_suggestions", sa.Column("recommendation", sa.String(20), nullable=True))
    op.add_column("skill_suggestions", sa.Column("recommendation_reason", sa.Text(), nullable=True))
    op.add_column("skill_suggestions", sa.Column("frequency_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("skill_suggestions", "frequency_count")
    op.drop_column("skill_suggestions", "recommendation_reason")
    op.drop_column("skill_suggestions", "recommendation")
