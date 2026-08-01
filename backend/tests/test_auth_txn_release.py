"""get_current_user must not pin a pooler slot for the whole request.

It reads the user (and, under governance, the active workspace) and then hands
control to a handler that may spend seconds in an LLM call, a Qdrant lookup or
a GCS read. Holding the read transaction across that pins a PgBouncer server
slot the entire time, so ~10 concurrent requests per pod exhausted the pool.

Ending it is not simply commit()/rollback(): both expire the identity map, and
the handler's first `current_user.x` read then issues a refresh SELECT that
opens a new transaction. These tests pin all four required properties.
"""

from sqlalchemy import Column, Integer, String, create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

import pytest

from backend.auth.dependencies import _end_read_transaction

Base = declarative_base()


class _User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String)
    org_id = Column(String)


@pytest.fixture
def db_and_queries():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    seed = Session()
    seed.add(_User(id=1, email="a@b.c", org_id="home-org"))
    seed.commit()
    seed.close()

    selects = []

    @event.listens_for(engine, "after_cursor_execute")
    def _record(conn, cursor, statement, *a):
        if statement.strip().upper().startswith("SELECT"):
            selects.append(statement)

    db = Session()
    yield db, selects, Session
    db.close()


def test_transaction_is_closed_afterwards(db_and_queries):
    db, _selects, _Session = db_and_queries
    db.query(_User).filter(_User.id == 1).first()
    assert db.in_transaction(), "precondition: the lookup opened a transaction"

    _end_read_transaction(db)

    assert not db.in_transaction(), (
        "the read transaction must be closed, or a transaction-mode pooler "
        "holds its server slot for the request's whole lifetime"
    )


def test_reading_the_user_afterwards_issues_no_extra_query(db_and_queries):
    """The property a bare commit()/rollback() fails.

    If the instance is expired, the handler's first attribute read refreshes
    it, opening a fresh transaction and undoing the release entirely.
    """
    db, selects, _Session = db_and_queries
    user = db.query(_User).filter(_User.id == 1).first()
    after_load = len(selects)

    _end_read_transaction(db)
    _ = user.email
    _ = user.org_id

    assert len(selects) == after_load, (
        f"attribute access triggered a refresh SELECT: {selects[after_load:]}"
    )
    assert not db.in_transaction(), "the refresh reopened a transaction"


def test_in_memory_org_override_is_not_persisted(db_and_queries):
    """The workspace override is deliberately in-memory only.

    get_current_user rewrites user.org_id to the active workspace — a mapped
    column that must never reach the database. Committing before that write is
    what keeps it out.
    """
    db, _selects, Session = db_and_queries
    user = db.query(_User).filter(_User.id == 1).first()

    _end_read_transaction(db)
    user.org_id = "active-workspace"  # as get_current_user does, after the commit

    assert user.org_id == "active-workspace", "override must be visible to handlers"

    check = Session()
    stored = check.query(_User).filter(_User.id == 1).first().org_id
    check.close()
    assert stored == "home-org", "the workspace override leaked into the database"


def test_handler_mutation_still_persists(db_and_queries):
    """api/memory.py mutates current_user then commits its own session.

    That only works while `user` stays attached to the request's session — the
    reason this fix is a commit rather than a separate short-lived session.
    """
    db, _selects, Session = db_and_queries
    user = db.query(_User).filter(_User.id == 1).first()

    _end_read_transaction(db)

    user.email = "changed@b.c"  # PUT /api/memory/soul shape
    db.commit()

    check = Session()
    stored = check.query(_User).filter(_User.id == 1).first().email
    check.close()
    assert stored == "changed@b.c"


def test_expire_on_commit_is_restored(db_and_queries):
    """Handler commits must keep default semantics.

    The suppression is scoped to this one commit; leaving it off would make
    every later handler commit skip invalidation and risk stale reads.
    """
    db, _selects, _Session = db_and_queries
    db.query(_User).filter(_User.id == 1).first()
    before = db.expire_on_commit

    _end_read_transaction(db)

    assert db.expire_on_commit is before is True
