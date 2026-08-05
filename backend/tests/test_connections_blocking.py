"""Connection routes must not run blocking work on the event loop, and must not
hold a pooler slot across a call to a customer's database.

Every handler in api/connections.py was `async def` with zero `await`s. FastAPI
routes `async def` straight onto the event loop, and the backend runs
UVICORN_WORKERS=1, so each one blocked the pod's only loop for the duration of
its work — health probes included. `refresh_connection_schema` is the worst:
schema discovery is ~6 round-trips per table against the customer's database,
so a few hundred tables freezes the loop for tens of seconds. That is the shape
of the 2026-07-23 liveness kill. Declared as plain `def`, Starlette runs them in
a threadpool instead and the loop stays free.

Separately, the handler's own session had an open read transaction from
`_find_connection` and held it across the connector call — on a transaction-mode
pooler that pins a scarce server slot for the whole network wait.
"""

import inspect

import pytest
from sqlalchemy import JSON, LargeBinary, create_engine
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from sqlalchemy.orm import sessionmaker

from backend.api import connections as conn_api
from backend.database.base import Base
from backend.models.database_connection import DatabaseConnection
from backend.models.user import User

USER_ID = "user-1"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    # Postgres-only column types across the shared metadata; swapped for their
    # portable equivalents so create_all works on SQLite. Mirrors the fixture
    # in tests/api/test_refresh_visibility.py.
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
                col.server_default = None
            elif isinstance(col.type, BYTEA):
                col.type = LargeBinary()
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def user(db):
    u = User(id=USER_ID, email="u@example.com", org_id=None)
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def connection(db, user):
    c = DatabaseConnection(
        user_id=USER_ID,
        name="prod",
        db_type="postgres",
        host="db.example.com",
        port=5432,
        database="app",
        username="reader",
        owner_scope_kind="user",
        owner_scope_id=USER_ID,
    )
    c.password = "secret"
    db.add(c)
    db.commit()
    # Force the handler's _find_connection to issue a real SELECT, so there is
    # genuinely an open transaction for the fix to end.
    db.expire_all()
    return c


class _FakeConnector:
    def test_connection(self):
        return True

    def test_write_access(self):
        return True

    def close(self):
        pass


# ---------------------------------------------------------------------------
# Handlers must not be coroutines
# ---------------------------------------------------------------------------


def test_no_connection_handler_runs_on_the_event_loop():
    """Guards the whole module, not just the handlers touched today.

    Every one of these does sync SQLAlchemy work and several make network calls
    to a customer database. A single `async def` reintroduces the freeze.
    """
    offenders = [
        route.endpoint.__name__
        for route in conn_api.router.routes
        if inspect.iscoroutinefunction(route.endpoint)
    ]

    assert offenders == [], (
        f"these handlers would block the event loop: {offenders}. "
        "Declare them `def` so Starlette runs them in a threadpool, or make "
        "the blocking part `await asyncio.to_thread(...)`."
    )


def test_the_router_actually_has_handlers():
    """Stops the guard above from passing on an empty list."""
    assert len(conn_api.router.routes) >= 20


# ---------------------------------------------------------------------------
# The read transaction must end before the connector call
# ---------------------------------------------------------------------------


def test_test_connection_releases_the_transaction_before_dialing(
    db, user, connection, monkeypatch
):
    seen = {}

    def _fake_get_connector(**_kwargs):
        seen["in_transaction"] = db.in_transaction()
        return _FakeConnector()

    monkeypatch.setattr(conn_api, "get_connector", _fake_get_connector)
    monkeypatch.setattr(conn_api, "get_connector_registration", lambda _t: None)

    result = conn_api.test_connection(str(connection.id), current_user=user, db=db)

    assert result.success is True
    assert seen["in_transaction"] is False, (
        "the read transaction must be closed before dialling the customer's "
        "database — otherwise a PgBouncer server slot is pinned for the whole "
        "connect timeout"
    )


def test_test_write_access_releases_the_transaction_before_dialing(
    db, user, connection, monkeypatch
):
    seen = {}

    def _fake_get_connector(**_kwargs):
        seen["in_transaction"] = db.in_transaction()
        return _FakeConnector()

    monkeypatch.setattr(conn_api, "get_connector", _fake_get_connector)

    result = conn_api.test_write_access(str(connection.id), current_user=user, db=db)

    assert result.success is True
    assert seen["in_transaction"] is False


def test_the_connection_stays_usable_after_the_release(db, user, connection, monkeypatch):
    """end_read_transaction must not expire the row.

    A bare commit()/rollback() would, and the handler's very next
    `connection.host` read would issue a refresh SELECT — reopening a
    transaction and taking back the exact slot the release just freed. So the
    property to assert is: zero queries between the release and the connector
    call.
    """
    from sqlalchemy import event

    statements = []
    at_release = {}
    real_end = conn_api.end_read_transaction

    def _spy_end(session):
        real_end(session)
        at_release["count"] = len(statements)

    def _fake_get_connector(**kwargs):
        # Every field the handler passes through — all read after the release.
        assert kwargs["host"] == "db.example.com"
        assert kwargs["database"] == "app"
        assert kwargs["password"] == "secret"
        return _FakeConnector()

    monkeypatch.setattr(conn_api, "end_read_transaction", _spy_end)
    monkeypatch.setattr(conn_api, "get_connector", _fake_get_connector)
    monkeypatch.setattr(conn_api, "get_connector_registration", lambda _t: None)

    engine = db.get_bind()

    @event.listens_for(engine, "after_cursor_execute")
    def _watch(_conn, _cursor, statement, *_a):
        if statement.strip().upper().startswith("SELECT"):
            statements.append(statement)

    conn_api.test_connection(str(connection.id), current_user=user, db=db)

    assert at_release, "the handler never called end_read_transaction"
    assert len(statements) == at_release["count"], (
        "reading the connection after the release re-queried, which reopens a "
        f"transaction: {statements[at_release['count']:]}"
    )


# ---------------------------------------------------------------------------
# The schema walk itself must be bounded server-side
# ---------------------------------------------------------------------------


class _FakeConn:
    def __init__(self):
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1


class _FakeCursor:
    """Answers the reltuples probe, then whatever `count_result` says."""

    def __init__(self, reltuples, count_result):
        self._reltuples = reltuples
        self._count_result = count_result
        self._pending = None
        self.connection = _FakeConn()
        self.executed: list[str] = []

    def execute(self, sql, _params=None):
        self.executed.append(sql)
        if sql.lstrip().upper().startswith("SET "):
            return  # session/transaction settings answer nothing
        if "pg_class" in sql:
            self._pending = [self._reltuples]
            return
        if isinstance(self._count_result, Exception):
            raise self._count_result
        self._pending = [self._count_result]

    def fetchone(self):
        return self._pending


def _pg():
    from backend.connectors.postgres import PostgresConnector

    return PostgresConnector(
        host="h", port=5432, database="d", username="u", password="p",
    )


def test_the_schema_path_is_capped_server_side():
    """execute_query issues `SET LOCAL statement_timeout`; the schema path never
    did, so its exact COUNT(*) fallback was unbounded on the server.

    The cap is applied per-transaction, not as a connection-level default: a
    `-c statement_timeout` startup option is refused outright by PgBouncer
    ("unsupported startup parameter: options"), which would stop every
    pooler-fronted source database from connecting at all.
    """
    from backend.config import settings

    kwargs = _pg()._get_connect_kwargs()
    assert "options" not in kwargs

    cursor = _FakeCursor(reltuples=0, count_result=17)
    conn = _pg()
    conn._get_connection = lambda: object()
    conn._get_cursor = lambda _c, dict_mode=False: cursor
    conn._schema_cursor()

    assert (
        f"SET LOCAL statement_timeout = '{settings.query_timeout_ms}'"
        in cursor.executed
    )


def test_row_count_uses_the_planner_estimate_and_never_scans():
    cursor = _FakeCursor(reltuples=4200, count_result=RuntimeError("must not scan"))

    assert _pg()._get_row_count(cursor, "public", "orders") == 4200


def test_a_never_analyzed_table_still_falls_back_to_an_exact_count():
    """reltuples <= 0 means never analyzed; the exact count is still correct
    behaviour when it is cheap enough to finish."""
    cursor = _FakeCursor(reltuples=0, count_result=17)

    assert _pg()._get_row_count(cursor, "public", "orders") == 17
    assert cursor.connection.rollbacks == 0


def test_a_timed_out_count_degrades_instead_of_failing_the_refresh():
    """With statement_timeout now set, a huge never-analyzed table raises
    instead of hanging. The count is a display hint, so one bad table must not
    take down the whole schema refresh — and the aborted transaction must be
    rolled back or every later table dies with 25P02.
    """
    cursor = _FakeCursor(
        reltuples=-1,
        count_result=Exception("canceling statement due to statement timeout"),
    )

    assert _pg()._get_row_count(cursor, "public", "events") == 0
    assert cursor.connection.rollbacks == 1, (
        "a failed COUNT(*) leaves the transaction ABORTED; without a rollback "
        "every remaining table in the walk fails with 25P02"
    )
