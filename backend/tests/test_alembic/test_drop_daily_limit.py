"""Postgres-backed checks for dr0pcap02 — drop user_credit_balances.daily_limit.

The migration is deliberately conditional in both directions, because databases
reach it in two different shapes: those that ran the original cr3d1tcap00 (which
dropped the column before it was neutralised) arrive with the column already
gone, and everything else arrives with it present. An unconditional
DROP COLUMN fails on the former with "column does not exist"; an unconditional
ADD COLUMN fails on the latter when downgrading. These tests pin both paths.

Runs against the configured database, following the pattern in
test_backfill_briefing_kind.py: drive real alembic up and down rather than
asserting on the migration source.
"""
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
import pytest

from backend.database.session import SessionLocal


REV_BEFORE = "cr3d1tcap01"   # column present
REV_DROP = "dr0pcap02"       # column dropped

_COLUMN_SQL = """
    SELECT data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'user_credit_balances' AND column_name = 'daily_limit'
"""


def _column():
    """The daily_limit column's definition, or None when it does not exist."""
    db = SessionLocal()
    try:
        return db.execute(text(_COLUMN_SQL)).fetchone()
    finally:
        db.close()


def _execute(sql: str, **params):
    db = SessionLocal()
    try:
        db.execute(text(sql), params)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def cfg():
    return Config("alembic.ini")


@pytest.fixture(autouse=True)
def _leave_at_head(cfg):
    """Each test walks the chain; put the database back at head afterwards so a
    failure here cannot strand the rest of the suite on an older revision."""
    yield
    command.upgrade(cfg, "head")


def test_single_head_containing_this_revision():
    """A second head would make `alembic upgrade head` ambiguous and fail the
    migrate Job before any pod rolls.

    Asserts the invariant (exactly one head) rather than the current revision
    id, so later migrations do not have to edit this test — but still checks
    dr0pcap02 is on the path to that head, which catches it being orphaned onto
    a branch of its own."""
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    heads = script.get_heads()
    assert len(heads) == 1, f"expected exactly one head, got {heads}"

    chain = {rev.revision for rev in script.iterate_revisions(heads[0], "base")}
    assert REV_DROP in chain, f"{REV_DROP} is not an ancestor of head {heads[0]}"


def test_drop_removes_column_when_present(cfg):
    command.downgrade(cfg, REV_BEFORE)
    assert _column() is not None, "precondition: column should exist at cr3d1tcap01"

    command.upgrade(cfg, REV_DROP)
    assert _column() is None


def test_drop_is_a_noop_when_column_is_already_absent(cfg):
    """The drifted case: a database that ran the original cr3d1tcap00 arrives
    here with the column already gone. The unconditional form raised
    UndefinedColumn; this must complete."""
    command.downgrade(cfg, REV_BEFORE)
    _execute("ALTER TABLE user_credit_balances DROP COLUMN daily_limit")
    assert _column() is None, "precondition: column should be gone"

    command.upgrade(cfg, REV_DROP)  # must not raise
    assert _column() is None


def test_downgrade_restores_the_original_column_definition(cfg):
    command.upgrade(cfg, REV_DROP)
    assert _column() is None

    command.downgrade(cfg, REV_BEFORE)
    col = _column()
    assert col is not None
    data_type, is_nullable, default = col
    assert data_type == "integer"
    assert is_nullable == "NO"
    assert "180" in (default or ""), f"expected server_default 180, got {default!r}"


def test_downgrade_backfills_existing_rows(cfg):
    """NOT NULL only holds on a populated table because the server_default
    backfills. A row inserted while the column is absent must come back with
    180 rather than blocking the downgrade."""
    command.upgrade(cfg, REV_DROP)

    db = SessionLocal()
    try:
        user = db.execute(text("SELECT id FROM users LIMIT 1")).fetchone()
        assert user, "need at least one user row for the FK"
        user_id = user[0]
    finally:
        db.close()

    _execute("DELETE FROM user_credit_balances WHERE user_id = :uid", uid=user_id)
    _execute(
        "INSERT INTO user_credit_balances (user_id, created_at) VALUES (:uid, NOW())",
        uid=user_id,
    )

    command.downgrade(cfg, REV_BEFORE)

    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT daily_limit FROM user_credit_balances WHERE user_id = :uid"),
            {"uid": user_id},
        ).fetchone()
    finally:
        db.close()
    assert row is not None and row[0] == 180


def test_upgrade_downgrade_is_repeatable(cfg):
    """Both statements are conditional, so cycling must not accumulate errors."""
    for _ in range(2):
        command.upgrade(cfg, REV_DROP)
        assert _column() is None
        command.downgrade(cfg, REV_BEFORE)
        assert _column() is not None
