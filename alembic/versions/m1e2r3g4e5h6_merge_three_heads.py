"""Merge a7b8c9d0e1f2 (drop_orphaned_default_org) with the post-#63 head.

Revision ID: m1e2r3g4e5h6
Revises: a7b8c9d0e1f2, mrgschemajson1
Create Date: 2026-05-26

After rebasing onto community dev (which already linearises dd9e8f7a6b5c +
sch1ma2jsonb3 via `mrgschemajson1_merge_schema_json_head`), the remaining
divergence is the `a7b8c9d0e1f2` branch added on this feature branch. This
merge joins them so `alembic upgrade head` resolves to a single head.
No DDL — history-linearisation only.
"""

from alembic import op

revision = "m1e2r3g4e5h6"
down_revision = ("a7b8c9d0e1f2", "mrgschemajson1")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
