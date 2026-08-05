"""Agent tools must not hold a pooled connection across work that isn't Postgres.

Two separate failures were live on the chat/EDA path, and both are guarded here.

1. *Pinning.* `execute_query` borrowed a session to look up the DatabaseConnection
   row, then kept it — transaction still open — across the remote read: Parquet
   over GCS, or a query against the customer's database. Seconds of network I/O
   with a PgBouncer server slot held by something doing no database work. Same
   shape in `profile_table` (across the whole table walk) and in
   `SummaryService.generate_or_update_summary`, which runs on the WebSocket
   handler's own session at the end of *every* chat turn and held its
   transaction across the summary LLM call.

2. *Nesting.* `get_plane_for_connection` had no `db` parameter and
   `get_connector_for_connection` had no `db_session` parameter, so resolving a
   plane-backed connector always opened a *second* session while the caller
   still held its first. Doubling peak checkouts is the mild part; the real
   hazard is that under contention the thread waits `db_pool_timeout` for the
   second slot while pinning the first, so nobody releases while everybody
   waits and they all shed 503s together.

`end_read_transaction` (not a bare commit/rollback) is what ends the transaction
without expiring loaded rows — `test_auth_txn_release.py` proves that property
for the helper itself, so it is not re-proven here.
"""

import pytest
from sqlalchemy import JSON, LargeBinary, create_engine
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from sqlalchemy.orm import sessionmaker

from backend.agents.context import AgentContext
from backend.agents.data_agent import tools as data_tools
from backend.database.base import Base
from backend.models.database_connection import DatabaseConnection
from backend.models.user import User

USER_ID = "user-1"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    # Postgres-only column types across the shared metadata, swapped for their
    # portable equivalents so create_all works on SQLite. Mirrors the fixture in
    # tests/test_connections_blocking.py.
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
def connection(db):
    db.add(User(id=USER_ID, email="u@example.com", org_id=None))
    c = DatabaseConnection(
        user_id=USER_ID,
        name="csv upload",
        db_type="dataset",
        host="",
        port=0,
        database="",
        username="",
        owner_scope_kind="user",
        owner_scope_id=USER_ID,
    )
    c.password = ""  # encrypting setter; the column is NOT NULL
    db.add(c)
    db.commit()
    # Force the tool's own lookup to issue a real SELECT, so there is genuinely
    # an open transaction for the release to end.
    db.expire_all()
    return c


class _Result:
    columns = ["n"]
    rows = [[1]]
    row_count = 1
    execution_time_ms = 1.0
    truncated = False


@pytest.fixture
def agent_tools(db, connection, monkeypatch):
    """The data-agent tools, wired to the test session and stubbed side channels."""
    monkeypatch.setattr(data_tools, "SessionLocal", lambda: db)
    # Redis-backed result side channel — not under test.
    monkeypatch.setattr(data_tools, "store_query_result", lambda *a, **k: None)
    monkeypatch.setattr(data_tools, "publish_query_result", lambda *a, **k: None)
    ctx = AgentContext(user_id=USER_ID, available_connections=[connection.id])
    return {t.name: t for t in data_tools.build_data_agent_tools(ctx)}


# ---------------------------------------------------------------------------
# Pinning: no open transaction across the remote read
# ---------------------------------------------------------------------------


def test_execute_query_releases_before_the_connector_runs(
    db, connection, agent_tools, monkeypatch
):
    seen = {}

    class _Connector:
        def execute_query(self, _sql):
            seen["in_transaction"] = db.in_transaction()
            return _Result()

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    # Plane path off — exercise the live source-DB branch, which is what runs in
    # production today.
    monkeypatch.setattr(data_tools, "_serve_query_via_dataplane", lambda *a, **k: None)
    monkeypatch.setattr(
        data_tools, "get_connector_for_connection", lambda _c, _db=None: _Connector()
    )
    # Lazily imported inside the tool, so patch it at its source module.
    import backend.services.llm_privacy as llm_privacy

    monkeypatch.setattr(llm_privacy, "metadata_only_for_connection", lambda _c: False)

    out = agent_tools["execute_query"].invoke(
        {"connection_id": connection.id, "sql": "SELECT 1"}
    )

    assert "error" not in out, out
    assert seen["in_transaction"] is False, (
        "execute_query held its read transaction across the connector call — "
        "that pins a pooler slot for the whole remote read"
    )


def test_profile_table_releases_before_the_table_walk(
    db, connection, agent_tools, monkeypatch
):
    seen = {}

    class _Connector:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(
        data_tools,
        "load_schema_file",
        lambda _cid: {"schemas": {"main": {"tables": {"t": {"columns": [], "row_count": 0}}}}},
    )
    monkeypatch.setattr(
        data_tools, "get_connector_for_connection", lambda _c, _db=None: _Connector()
    )
    monkeypatch.setattr(data_tools, "get_connector_registration", lambda _t: None)
    # Lazily imported inside the tool, so patch it at its source module.
    import backend.services.llm_privacy as llm_privacy

    monkeypatch.setattr(llm_privacy, "metadata_only_for_connection", lambda _c: False)

    def _fake_profile(**_kwargs):
        seen["in_transaction"] = db.in_transaction()
        return {"row_count": 0, "columns": []}

    import backend.services.table_profiler as profiler

    monkeypatch.setattr(profiler, "profile_table", _fake_profile)

    out = agent_tools["profile_table"].invoke(
        {"connection_id": connection.id, "table_name": "t"}
    )

    assert "error" not in out, out
    assert seen["in_transaction"] is False, (
        "profile_table held its read transaction across the profiling walk"
    )


@pytest.mark.asyncio
async def test_summary_releases_before_the_llm_call(db, monkeypatch):
    """This one runs on the WS handler's session at the end of every chat turn."""
    import backend.llm.factory as llm_factory
    from backend.models.conversation import Conversation
    from backend.services.summary_service import SummaryService

    conv = Conversation(user_id=USER_ID, thread_id="t-1", title="x")
    db.add(conv)
    db.commit()
    db.expire_all()

    seen = {}

    class _Provider:
        async def chat(self, _messages, **_kwargs):
            seen["in_transaction"] = db.in_transaction()
            return "a summary"

    # get_provider is imported inside the method, so patch it at its source.
    monkeypatch.setattr(llm_factory, "get_provider", lambda *a, **k: _Provider())

    await SummaryService.generate_or_update_summary(db, conv.id, "q", "a")

    assert seen["in_transaction"] is False, (
        "the turn summary held a transaction across the LLM call"
    )
    assert (
        SummaryService.get_summary(db, conv.id).summary_text == "a summary"
    ), "releasing must not stop the write from landing afterwards"


# ---------------------------------------------------------------------------
# Nesting: helpers must reuse the caller's session, not open a second one
# ---------------------------------------------------------------------------


def test_get_plane_for_connection_forwards_the_session(connection, monkeypatch):
    import importlib
    import sys

    # tests/services/test_resource_lifecycle.py:18 does
    # `sys.modules['backend.services.data_plane_service'] = MagicMock()` at import
    # time and never restores it, so in a full-suite run this module may already
    # be a mock. Drop it and re-import the real one; monkeypatch.delitem puts the
    # original entry back afterwards, so we don't make the hygiene problem worse.
    monkeypatch.delitem(sys.modules, "backend.services.data_plane_service", raising=False)
    dps = importlib.import_module("backend.services.data_plane_service")

    seen = {}

    def _fake_default_plane(_scope, db=None):
        seen["db"] = db
        return object()

    monkeypatch.setattr(dps, "get_default_plane", _fake_default_plane)
    sentinel = object()

    dps.get_plane_for_connection(connection, sentinel)

    assert seen["db"] is sentinel, (
        "get_plane_for_connection dropped the caller's session, so "
        "get_default_plane opens a second checkout while the first is held"
    )


def test_get_connector_for_connection_forwards_the_session(connection, monkeypatch):
    from backend.connectors import factory

    seen = {}

    class _Reg:
        class connector_class:
            @classmethod
            def from_connection(cls, _connection, db_session=None):
                seen["db_session"] = db_session
                return "connector"

    monkeypatch.setitem(factory._CONNECTORS, "dataset", _Reg)
    sentinel = object()

    assert factory.get_connector_for_connection(connection, sentinel) == "connector"
    assert seen["db_session"] is sentinel, (
        "the factory dropped the caller's session; plane-backed connectors then "
        "resolve their DataPlane on a second checkout"
    )


# ---------------------------------------------------------------------------
# Leak: the mesh runtime helper must close what it opens
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("runtime_raises", [False, True])
async def test_run_via_mesh_runtime_closes_its_session(monkeypatch, runtime_raises):
    from backend.agents import invoke_helpers

    closed = {"n": 0}

    class _Session:
        def close(self):
            closed["n"] += 1

    class _Runtime:
        def __init__(self, **_kwargs):
            pass

        async def execute(self, *_a):
            if runtime_raises:
                raise RuntimeError("boom")
            return {"success": True}

    monkeypatch.setattr(
        "backend.agents.runtime.AgentRuntime", _Runtime, raising=False
    )
    monkeypatch.setattr(
        "backend.services.agent_registry.AgentRegistry",
        lambda: type("R", (), {"redis": None})(),
        raising=False,
    )
    monkeypatch.setattr(
        "backend.services.agent_message_bus.AgentMessageBus",
        lambda **_kwargs: object(),
        raising=False,
    )

    call = invoke_helpers.run_via_mesh_runtime(
        agent_type="data_agent",
        user_id=USER_ID,
        session_id="s-1",
        context=None,
        message="hi",
        tools=[],
        system_prompt="",
        db_session_factory=_Session,
    )
    if runtime_raises:
        with pytest.raises(RuntimeError):
            await call
    else:
        await call

    assert closed["n"] == 1, (
        "run_via_mesh_runtime leaked its session — every mesh invocation would "
        "drain one checkout permanently"
    )
