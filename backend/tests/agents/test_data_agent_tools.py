"""Tests for the data-agent plane-redirect path in `execute_query`.

`_serve_query_via_dataplane` mirrors the dashboard widget plane-serve gating:
flag off → None; no pipelines → None; local plane cold → None; local plane warm
→ runs DuckDB query; GCS plane → reader.query; reader None / exception → None.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import backend.agents.data_agent.tools as tools


# ── Fixtures ────────────────────────────────────────────────────────────────

def _conn(org_id="org-1", connection_id=42, user_id="u-1"):
    return SimpleNamespace(id=connection_id, user_id=user_id, org_id=org_id)


def _patch(monkeypatch, **overrides):
    """Patch every external dep `_serve_query_via_dataplane` reaches for.

    Lazy imports inside the helper mean we patch the source modules, not the
    `tools` namespace.
    """
    monkeypatch.setattr(
        "backend.config.feature_flags.enabled",
        overrides.get("flag", lambda *a, **kw: True),
    )
    monkeypatch.setattr(
        "backend.services.data_plane_service.plane_table_map",
        overrides.get("table_map", lambda c, db: {"orders": "acme__orders"}),
    )
    monkeypatch.setattr(
        "backend.utils.sql_refs.rewrite_table_refs",
        overrides.get("rewrite", lambda sql, m, allowed_schemas=None: (sql, {})),
    )
    monkeypatch.setattr(
        "backend.utils.sql_refs.extract_table_refs",
        overrides.get("extract", lambda sql: ["acme__orders"]),
    )
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_plane_for_connection",
        # Takes the caller's session so it doesn't open a second checkout while
        # the first is still held.
        overrides.get("get_plane", lambda c, db=None: (MagicMock(), MagicMock())),
    )
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_gcs_duckdb_reader",
        overrides.get("get_reader", lambda scope, db=None: None),
    )


# ── Gate paths ─────────────────────────────────────────────────────────────

def test_returns_none_when_org_id_missing(monkeypatch):
    _patch(monkeypatch)
    assert tools._serve_query_via_dataplane(_conn(org_id=None), "SELECT 1", MagicMock()) is None


def test_returns_none_when_flag_disabled(monkeypatch):
    _patch(monkeypatch, flag=lambda *a, **kw: False)
    assert tools._serve_query_via_dataplane(_conn(), "SELECT 1", MagicMock()) is None


def test_returns_none_when_no_pipelines(monkeypatch):
    _patch(monkeypatch, table_map=lambda c, db: {})
    assert tools._serve_query_via_dataplane(_conn(), "SELECT 1", MagicMock()) is None


def test_returns_none_when_rewrite_raises(monkeypatch):
    def _boom(sql, m, allowed_schemas=None):
        raise ValueError("unparseable")
    _patch(monkeypatch, rewrite=_boom)
    assert tools._serve_query_via_dataplane(_conn(), "SELECT 1", MagicMock()) is None


# ── Local plane ────────────────────────────────────────────────────────────

def test_local_plane_cold_returns_none(monkeypatch):
    from backend.data_plane.local_filesystem import LocalFilesystemDataPlane

    plane = MagicMock(spec=LocalFilesystemDataPlane)
    plane.table_exists.return_value = False
    scope = MagicMock()
    _patch(monkeypatch, get_plane=lambda c, db=None: (plane, scope))

    assert tools._serve_query_via_dataplane(_conn(), "SELECT 1 FROM orders", MagicMock()) is None
    plane.query.assert_not_called()


def test_local_plane_warm_runs_query(monkeypatch):
    from backend.connectors.base import QueryResult
    from backend.data_plane.local_filesystem import LocalFilesystemDataPlane

    plane = MagicMock(spec=LocalFilesystemDataPlane)
    plane.table_exists.return_value = True
    qr = QueryResult(columns=["c"], rows=[(1,)], row_count=1, execution_time_ms=2.0)
    plane.query.return_value = qr
    scope = MagicMock()
    _patch(monkeypatch, get_plane=lambda c, db=None: (plane, scope))

    result = tools._serve_query_via_dataplane(_conn(), "SELECT 1 FROM orders", MagicMock())
    assert result is qr
    plane.query.assert_called_once()


def test_local_plane_query_exception_returns_none(monkeypatch):
    from backend.data_plane.local_filesystem import LocalFilesystemDataPlane

    plane = MagicMock(spec=LocalFilesystemDataPlane)
    plane.table_exists.return_value = True
    plane.query.side_effect = RuntimeError("duckdb boom")
    _patch(monkeypatch, get_plane=lambda c, db=None: (plane, MagicMock()))

    assert tools._serve_query_via_dataplane(_conn(), "SELECT 1", MagicMock()) is None


# ── GCS plane (prod) ───────────────────────────────────────────────────────

def test_gcs_reader_none_returns_none(monkeypatch):
    """Non-local plane + reader factory returns None → residency-locked → fall back."""
    plane = MagicMock()  # not a LocalFilesystemDataPlane
    _patch(monkeypatch, get_plane=lambda c, db=None: (plane, MagicMock()), get_reader=lambda scope, db=None: None)

    assert tools._serve_query_via_dataplane(_conn(), "SELECT 1", MagicMock()) is None


def test_gcs_reader_runs_and_closes(monkeypatch):
    from backend.connectors.base import QueryResult

    plane = MagicMock()  # not Local
    qr = QueryResult(columns=["x"], rows=[("a",)], row_count=1, execution_time_ms=5.0)
    reader = MagicMock()
    reader.query.return_value = qr
    _patch(
        monkeypatch,
        get_plane=lambda c, db=None: (plane, MagicMock()),
        get_reader=lambda scope, db=None: reader,
    )

    result = tools._serve_query_via_dataplane(_conn(), "SELECT 1", MagicMock())
    assert result is qr
    reader.query.assert_called_once()
    reader.close.assert_called_once()


def test_gcs_reader_exception_returns_none_and_closes(monkeypatch):
    plane = MagicMock()
    reader = MagicMock()
    reader.query.side_effect = RuntimeError("gcs boom")
    _patch(
        monkeypatch,
        get_plane=lambda c, db=None: (plane, MagicMock()),
        get_reader=lambda scope, db=None: reader,
    )

    assert tools._serve_query_via_dataplane(_conn(), "SELECT 1", MagicMock()) is None
    reader.close.assert_called_once()


# ── execute_query integration: serve path bypasses connector ───────────────

def test_execute_query_uses_plane_when_serve_succeeds(monkeypatch):
    """If `_serve_query_via_dataplane` returns a QueryResult, the live source
    connector must NOT be opened."""
    from backend.agents.context import AgentContext
    from backend.connectors.base import QueryResult

    ctx = AgentContext(user_id="u-1", available_connections=[42])
    qr = QueryResult(columns=["c"], rows=[(1,)], row_count=1, execution_time_ms=1.0)

    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = _conn()
    monkeypatch.setattr("backend.agents.data_agent.tools.SessionLocal", lambda: fake_db)

    connector_factory = MagicMock(side_effect=AssertionError("must not open connector"))
    monkeypatch.setattr("backend.agents.data_agent.tools.get_connector_for_connection", connector_factory)

    monkeypatch.setattr(
        "backend.agents.data_agent.tools._serve_query_via_dataplane",
        lambda conn, sql, db: qr,
    )
    monkeypatch.setattr("backend.agents.data_agent.tools.store_query_result", MagicMock())
    monkeypatch.setattr("backend.agents.data_agent.tools.publish_query_result", MagicMock())

    tools_list = tools.build_data_agent_tools(ctx)
    exec_tool = next(t for t in tools_list if t.name == "execute_query")
    out = exec_tool.invoke({"connection_id": 42, "sql": "SELECT 1"})

    assert out["row_count"] == 1
    assert out["columns"] == ["c"]
    connector_factory.assert_not_called()


def test_execute_query_falls_back_to_connector_when_serve_returns_none(monkeypatch):
    from backend.agents.context import AgentContext
    from backend.connectors.base import QueryResult

    ctx = AgentContext(user_id="u-1", available_connections=[42])
    qr = QueryResult(columns=["c"], rows=[(2,)], row_count=1, execution_time_ms=3.0)

    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = _conn()
    monkeypatch.setattr("backend.agents.data_agent.tools.SessionLocal", lambda: fake_db)

    connector = MagicMock()
    connector.execute_query.return_value = qr
    cm = MagicMock()
    cm.__enter__.return_value = connector
    cm.__exit__.return_value = False
    monkeypatch.setattr(
        "backend.agents.data_agent.tools.get_connector_for_connection",
        lambda c, db=None: cm,
    )

    monkeypatch.setattr(
        "backend.agents.data_agent.tools._serve_query_via_dataplane",
        lambda conn, sql, db: None,
    )
    monkeypatch.setattr("backend.agents.data_agent.tools.store_query_result", MagicMock())
    monkeypatch.setattr("backend.agents.data_agent.tools.publish_query_result", MagicMock())

    tools_list = tools.build_data_agent_tools(ctx)
    exec_tool = next(t for t in tools_list if t.name == "execute_query")
    out = exec_tool.invoke({"connection_id": 42, "sql": "SELECT 2"})

    assert out["row_count"] == 1
    assert out["rows"] == [[2]]
    connector.execute_query.assert_called_once_with("SELECT 2")


# ── execute_query: export-file label ───────────────────────────────────────
#
# `label` never reaches the tool's return value — it only rides along in the
# payload handed to store_query_result / publish_query_result, which is what
# the frontend names export files from. So assert on the published payload.

def _run_execute_query(monkeypatch, sql):
    """Invoke execute_query over a stubbed connector; return the published payload."""
    from backend.agents.context import AgentContext
    from backend.connectors.base import QueryResult

    ctx = AgentContext(user_id="u-1", available_connections=[42])
    qr = QueryResult(columns=["c"], rows=[(1,)], row_count=1, execution_time_ms=1.0)

    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = _conn()
    monkeypatch.setattr("backend.agents.data_agent.tools.SessionLocal", lambda: fake_db)
    monkeypatch.setattr(
        "backend.agents.data_agent.tools._serve_query_via_dataplane",
        lambda conn, sql, db: qr,
    )
    publish = MagicMock()
    monkeypatch.setattr("backend.agents.data_agent.tools.store_query_result", MagicMock())
    monkeypatch.setattr("backend.agents.data_agent.tools.publish_query_result", publish)

    tools_list = tools.build_data_agent_tools(ctx)
    exec_tool = next(t for t in tools_list if t.name == "execute_query")
    exec_tool.invoke({"connection_id": 42, "sql": sql})

    publish.assert_called_once()
    return publish.call_args.args[2]


def test_label_is_the_referenced_table(monkeypatch):
    payload = _run_execute_query(monkeypatch, "SELECT * FROM orders WHERE id = 1")
    assert payload["label"] == "orders"


def test_label_is_lowercased_and_ignores_schema_qualifier(monkeypatch):
    payload = _run_execute_query(monkeypatch, "SELECT * FROM Analytics.Orders")
    assert payload["label"] == "orders"


def test_label_falls_back_to_query_when_no_table_ref(monkeypatch):
    payload = _run_execute_query(monkeypatch, "SELECT 1")
    assert payload["label"] == "query"


def test_label_falls_back_to_query_when_sql_unparseable(monkeypatch):
    # extract_table_refs swallows parse errors and returns [] → fallback applies.
    payload = _run_execute_query(monkeypatch, "SELECT FROM WHERE ((")
    assert payload["label"] == "query"


def test_label_on_join_is_alphabetically_first_not_the_driving_table(monkeypatch):
    """Pins real behaviour: extract_table_refs sorts, so tables[0] is the
    alphabetically-first ref, not the FROM table."""
    payload = _run_execute_query(
        monkeypatch, "SELECT * FROM orders o JOIN customers c ON c.id = o.customer_id"
    )
    assert payload["label"] == "customers"


# --- the chat bubble needs to know the LLM was denied the rows ---------------


def test_published_payload_carries_values_withheld(monkeypatch):
    """The floor is on by default, so the side-channel must say so: the bubble
    renders the table itself precisely when the LLM could not."""
    payload = _run_execute_query(monkeypatch, "SELECT c FROM t")
    assert payload["values_withheld"] is True


def test_values_withheld_is_false_when_the_floor_is_off(monkeypatch):
    """With the floor off the LLM has the rows and writes its own markdown
    table — the bubble must not render a second one."""
    monkeypatch.setattr(
        "backend.services.llm_privacy.metadata_only_for_connection", lambda c: False
    )
    payload = _run_execute_query(monkeypatch, "SELECT c FROM t")
    assert payload["values_withheld"] is False
