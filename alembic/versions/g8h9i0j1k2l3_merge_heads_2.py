"""merge heads — join e6g7h8i9j0k1 and r1z2drift00

Revision ID: g8h9i0j1k2l3
Revises: e6g7h8i9j0k1, r1z2drift00
Create Date: 2026-05-22

Merges two diverged Alembic heads so `alembic upgrade head` works without
specifying a branch. No DDL — this is a history-linearisation commit only.
"""
from alembic import op


revision = "g8h9i0j1k2l3"
down_revision = ("e6g7h8i9j0k1", "r1z2drift00")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
