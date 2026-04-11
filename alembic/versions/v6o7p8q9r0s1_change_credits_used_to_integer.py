"""change credits_used column type from Float to Integer in credit_usage

Revision ID: v6o7p8q9r0s1
Revises: u5n6o7p8q9r0
Create Date: 2026-04-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "v6o7p8q9r0s1"
down_revision = "u5n6o7p8q9r0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "credit_usage",
        "credits_used",
        type_=sa.Integer(),
        existing_type=sa.Float(),
        postgresql_using="CEIL(credits_used)::INTEGER",
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "credit_usage",
        "credits_used",
        type_=sa.Float(),
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
