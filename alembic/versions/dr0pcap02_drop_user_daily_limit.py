"""Release 2: drop user_credit_balances.daily_limit.

Revision ID: dr0pcap02
Revises: cr3d1tcap01
Create Date: 2026-08-05

The contract half of removing the per-user daily credit cap. The expand half —
code that no longer reads the column — shipped in release 1; this drops the
column once that code is deployed everywhere.

DO NOT MERGE OR DEPLOY THIS BEFORE RELEASE 1 IS LIVE ON EVERY BACKEND REPLICA.
``scripts/deploy-k8s.sh`` runs the migrate Job to completion *before* rolling
the backend Deployment, and ``k8s/base/backend.yaml`` rolls with maxSurge: 0 /
maxUnavailable: 1, so a pod on the previous image serves for the whole rollout.
If that previous image still reads the column, this drop returns 500s from
GET /api/credits/balance — an endpoint hit on every page load and after every
chat turn — for the length of the deploy. That is the failure release 1 exists
to prevent; dropping early reintroduces it.

Conditional in both directions. A database healed by cr3d1tcap01 is
indistinguishable from one that never drifted, but anything that skipped that
repair — a restored snapshot, a manual stamp — would make an unconditional
drop fail with "column does not exist", and an unconditional re-add fail with
"column already exists".

Rollback policy — what downgrade() does and does not give back:

  * It restores the column's *definition*: INTEGER NOT NULL DEFAULT 180,
    matching t4n5o6p7q8r9_add_credit_system_tables.
  * It does NOT restore per-user values. Every row comes back at the default.
    The column has been write-only since spending moved to the org credit pool
    (backend/services/org_credit_pool.py), so nothing reads those numbers and
    nothing behaves differently for having lost them. Restoring them would mean
    keeping a backup of a column no code consults; we accept the loss instead.
  * ADD COLUMN IF NOT EXISTS skips an existing column without inspecting it, so
    a database carrying a hand-altered daily_limit — different type, nullable —
    keeps its own version rather than being normalised. That is deliberate: a
    migration should not silently rewrite a column it did not create. Anything
    in that state needs manual repair, and backend/tests/test_alembic/
    test_drop_daily_limit.py pins the definition this migration expects.

Restoring the per-user cap as a feature would need a new migration plus new
code; this downgrade only exists to unblock a rollback of the schema.
"""

from alembic import op


revision = "dr0pcap02"
down_revision = "cr3d1tcap01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_credit_balances DROP COLUMN IF EXISTS daily_limit")


def downgrade() -> None:
    # Matches the original definition in t4n5o6p7q8r9_add_credit_system_tables.
    # server_default backfills existing rows so the NOT NULL holds.
    op.execute(
        "ALTER TABLE user_credit_balances "
        "ADD COLUMN IF NOT EXISTS daily_limit INTEGER NOT NULL DEFAULT 180"
    )
