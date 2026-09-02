"""`materialize_dashboard` reads and writes under two different scopes.

The DuckDB-over-GCS warm has to read the source Parquet from the *connection's*
scope — that's where the Pipeline wrote it. The `_dash_*` cache it produces is
written under the *dashboard owner's org* scope, which is what serves the widget.
Using one scope for both silently misses the Parquet and falls back to a
per-widget source query, so the fast path quietly stops being used.
"""
from unittest.mock import MagicMock, patch

import pytest

from backend.data_plane.scope import OwnerScope


ORG_ID = "org-1"
CONNECTION_OWNER = "user-9"


@pytest.fixture
def wiring():
    """Patch everything `materialize_dashboard` reaches for, and hand back the
    plane + DuckDB reader doubles so tests can assert the scopes they saw."""
    dashboard = MagicMock(id=7, user_id="user-1", cache_date_range_days=90, data_context=None)
    dashboard.widgets = [
        {"id": "w1", "dataSource": {"connectionId": 3, "sql": "SELECT 1 FROM orders"}},
    ]
    # Connection owned by a *different* scope than the dashboard's org.
    connection = MagicMock(
        id=3, db_type="postgres", user_id=CONNECTION_OWNER,
        org_id=None, owner_scope_kind="user", owner_scope_id=CONNECTION_OWNER,
    )

    db = MagicMock()

    def _query(model):
        qs = MagicMock()
        name = getattr(model, "__tablename__", getattr(model, "__name__", ""))
        qs.filter.return_value.first.return_value = (
            dashboard if "dashboard" in name.lower() else connection
        )
        return qs

    db.query = MagicMock(side_effect=_query)

    plane = MagicMock()
    reader = MagicMock()
    reader.query.return_value = MagicMock(rows=[(1,)], columns=["n"], row_count=1)

    session_local = MagicMock(return_value=db)

    with patch("backend.database.session.SessionLocal", session_local), \
         patch("backend.services.dashboard_cache._get_org_for_user", return_value=ORG_ID), \
         patch("backend.services.data_plane_service.get_default_plane", return_value=plane), \
         patch("backend.services.data_plane_service.get_gcs_duckdb_reader", return_value=reader), \
         patch("backend.services.data_plane_service.plane_table_map", return_value={}), \
         patch("backend.config.feature_flags.enabled", return_value=True), \
         patch("backend.connectors.factory.get_connector_for_connection"), \
         patch("backend.connectors.factory.get_connector_registration", return_value=None), \
         patch("backend.services.dashboard_cache._is_pipeline_output_widget", return_value=False), \
         patch("backend.services.widget_result_cache.bump_generation"):
        yield plane, reader, dashboard


def test_duckdb_warm_reads_under_the_connection_scope(wiring):
    from backend.services.dashboard_cache import materialize_dashboard

    plane, reader, _dashboard = wiring
    result = materialize_dashboard(7)

    assert result.widgets_succeeded == 1, result.widget_errors
    reader.query.assert_called_once()
    assert reader.query.call_args[0][0] == OwnerScope("user", CONNECTION_OWNER)


def test_cache_table_is_written_under_the_dashboard_org_scope(wiring):
    """The write target must stay the org scope — that's the scope the widget
    read path resolves `_dash_*` against."""
    from backend.services.dashboard_cache import materialize_dashboard

    plane, reader, _dashboard = wiring
    materialize_dashboard(7)

    plane.write_parquet.assert_called_once()
    scope, table_name, _arrow = plane.write_parquet.call_args[0]
    assert scope == OwnerScope("org", ORG_ID)
    assert table_name == "_dash_7__w1"


def test_source_connector_is_used_when_duckdb_read_fails(wiring):
    """A DuckDB miss must not fail the widget — it falls back to the source."""
    from backend.services.dashboard_cache import materialize_dashboard

    plane, reader, _dashboard = wiring
    reader.query.side_effect = RuntimeError("no such table")

    with patch("backend.connectors.factory.get_connector_for_connection") as get_conn:
        get_conn.return_value.execute_query.return_value = MagicMock(
            rows=[(2,)], columns=["n"], row_count=1,
        )
        result = materialize_dashboard(7)

    assert result.widgets_succeeded == 1, result.widget_errors
    plane.write_parquet.assert_called_once()


def test_numeric_widget_id_materializes(wiring):
    """Agent-generated dashboards store numeric widget ids — the sanitizer
    must stringify them, not crash on int.lower()."""
    from backend.services.dashboard_cache import materialize_dashboard

    plane, reader, dashboard = wiring
    dashboard.widgets = [
        {"id": 9329, "dataSource": {"connectionId": 3, "sql": "SELECT 1 FROM orders"}},
    ]

    result = materialize_dashboard(7)

    assert result.widgets_succeeded == 1, result.widget_errors
    plane.write_parquet.assert_called_once()
    _scope, table_name, _arrow = plane.write_parquet.call_args[0]
    assert table_name == "_dash_7__w_9329"
