"""Drop user_credit_balances.daily_limit (per-user daily cap removed).

The per-user daily credit cap stopped gating anything when spending moved to
the per-org credit pool (see backend/services/org_credit_pool.py). The column
survived as a write-only field: settable from the admin UI, echoed in a few
tables, read by nothing that blocked a request. Its last reader was the
"no org pool" fallback in GET /api/credits/balance, which reported it as a
`remaining` balance even though it capped nothing.

The rest of user_credit_balances stays: the row is still created per user by
CreditService.get_or_create_balance. credit_usage — the actual spend ledger —
is untouched.

Revision ID: cr3d1tcap00
Revises: w1dgc4p0001
Create Date: 2026-08-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "cr3d1tcap00"
down_revision = "w1dgc4p0001"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("user_credit_balances", "daily_limit")


def downgrade():
    # Matches the original definition in t4n5o6p7q8r9_add_credit_system_tables.
    # server_default backfills existing rows so the NOT NULL holds.
    op.add_column(
        "user_credit_balances",
        sa.Column(
            "daily_limit",
            sa.Integer(),
            nullable=False,
            server_default="180",
        ),
    )
