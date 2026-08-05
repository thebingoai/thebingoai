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
from sqlalchemy.orm.attributes import set_committed_value

import pytest

from backend.database.session import end_read_transaction

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

    end_read_transaction(db)

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

    end_read_transaction(db)
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

    end_read_transaction(db)
    user.org_id = "active-workspace"  # as get_current_user does, after the commit

    assert user.org_id == "active-workspace", "override must be visible to handlers"

    check = Session()
    stored = check.query(_User).filter(_User.id == 1).first().org_id
    check.close()
    assert stored == "home-org", "the workspace override leaked into the database"


def test_the_override_survives_a_later_handler_commit(db_and_queries):
    """The case the test above does not reach — and the one that bites.

    Committing before the override keeps it out of *that* commit, but the
    override still leaves the User dirty, and FastAPI caches get_db per request:
    the handler goes on to use the same session. Any db.commit() it makes
    (api/memory.py's soul and preferences writes do exactly this) flushes the
    selected workspace over users.org_id permanently.

    That is durable cross-tenant access, not just a stale column —
    resolve_active_workspace returns `_role_in(home_org) or "member"`, so once
    home_org points at someone else's org the user keeps a fallback 'member'
    role there even after their membership row is deleted.

    Asserting on the response body would not catch this; only the stored row does.
    """
    db, _selects, Session = db_and_queries
    user = db.query(_User).filter(_User.id == 1).first()

    end_read_transaction(db)
    # Exactly what _resolve_local_user does for an X-Workspace-Id request.
    set_committed_value(user, "org_id", "active-workspace")

    # ...and then the handler writes something unrelated, as PUT /api/memory/soul does.
    user.email = "changed@b.c"
    db.commit()

    check = Session()
    row = check.query(_User).filter(_User.id == 1).first()
    stored_org, stored_email = row.org_id, row.email
    check.close()

    assert stored_email == "changed@b.c", "the handler's own write must still persist"
    assert stored_org == "home-org", (
        "the workspace override was flushed by the handler's commit — the user's "
        "home org is now someone else's workspace"
    )


def test_handler_mutation_still_persists(db_and_queries):
    """api/memory.py mutates current_user then commits its own session.

    That only works while `user` stays attached to the request's session — the
    reason this fix is a commit rather than a separate short-lived session.
    """
    db, _selects, Session = db_and_queries
    user = db.query(_User).filter(_User.id == 1).first()

    end_read_transaction(db)

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

    end_read_transaction(db)

    assert db.expire_on_commit is before is True
