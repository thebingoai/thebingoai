"""Idempotently restore user_credit_balances.daily_limit.

Revision ID: cr3d1tcap01
Revises: cr3d1tcap00
Create Date: 2026-08-05

Heals databases that ran ``cr3d1tcap00`` while it still dropped the column.
Neutralising that revision was not enough on its own: such a database is
already stamped ``cr3d1tcap00``, so alembic considers it applied and never
re-runs it, leaving the column gone. Release 1's premise — the column is
present, so the previous release's code keeps working through a rollout — is
false on exactly those databases unless something puts it back.

ADD COLUMN IF NOT EXISTS, so this is a silent no-op on a healthy database.
The column's values carry no meaning (nothing has read them since spending
moved to the org credit pool), so a drifted database losing the old numbers
costs nothing — the server_default backfills every row and the NOT NULL holds.

``downgrade()`` is empty, matching r1z2drift00_repair_timezone_columns: this
revision exists to repair drift, and undoing it would only recreate the drift.

NOTE for the release-2 migration that finally drops this column: it MUST use
``DROP COLUMN IF EXISTS``. A database healed here is indistinguishable from one
that was never drifted, but anything that skips this repair — a restored
snapshot, a manual stamp — would make an unconditional drop fail with
"column does not exist".
"""

from alembic import op


revision = "cr3d1tcap01"
down_revision = "cr3d1tcap00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE user_credit_balances "
        "ADD COLUMN IF NOT EXISTS daily_limit INTEGER NOT NULL DEFAULT 180"
    )


def downgrade() -> None:
    pass
