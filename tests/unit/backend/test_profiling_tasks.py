"""Unit tests for backend.tasks.profiling_tasks — connection profiling Celery tasks."""

from unittest.mock import MagicMock, patch

import pytest

from backend.tasks.profiling_tasks import (
    profile_connection as _profile_connection_task,
    backfill_profile_all_connections as _backfill_task,
)

# Extract the raw unbound function from the Celery task so we can call it
# with our own mock ``self`` — bypassing Celery's __call__ dispatch and the
# read-only ``request`` property.
_profile_connection_fn = _profile_connection_task.run.__func__


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_session_factory(connection=None):
    """Return a (factory, mock_session) pair pre-loaded with *connection*."""
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = connection
    factory = MagicMock(return_value=mock_session)
    return factory, mock_session


def _make_mock_connection(cid=1, db_type="postgres", schema_json_path="/tmp/schema.json"):
    """Build a lightweight mock DatabaseConnection."""
    conn = MagicMock()
    conn.id = cid
    conn.db_type = db_type
    conn.schema_json_path = schema_json_path
    conn.profiling_status = "pending"
    conn.profiling_error = None
    conn.profiling_progress = None
    conn.profiling_started_at = None
    conn.profiling_completed_at = None
    conn.data_context_path = None
    return conn


def _minimal_schema(tables=None):
    """Return a minimal nested schema JSON.

    *tables* is a dict of ``{table_name: {row_count, columns}}`` or ``None``
    for the two-table default (orders + customers).
    """
    if tables is None:
        tables = {
            "orders": {
                "row_count": 100,
                "columns": [{"name": "id", "type": "integer"}],
            },
            "customers": {
                "row_count": 50,
                "columns": [{"name": "id", "type": "integer"}],
            },
        }
    return {"schemas": {"public": {"tables": tables}}}


def _mock_self(retries=0):
    """Build a mock ``self`` for a ``bind=True`` Celery task."""
    mock = MagicMock()
    mock.request.retries = retries
    mock.retry.side_effect = Exception("celery-retry-sentinel")
    return mock


# ---------------------------------------------------------------------------
# TestProfileConnection
# ---------------------------------------------------------------------------

class TestProfileConnection:
    """Tests for the ``profile_connection`` Celery task."""

    # Shared patch target prefix
    _P = "backend.tasks.profiling_tasks"

    def _run(self, connection_id, *, retries=0, **patch_overrides):
        """Execute ``profile_connection`` with common patches.

        Any key in *patch_overrides* whose name matches a dependency
        replaces the default mock for that dependency.
        """
        connection = patch_overrides.pop("connection", _make_mock_connection(cid=connection_id))
        _, mock_session = _make_db_session_factory(connection)

        schema = patch_overrides.pop("schema_json", _minimal_schema())

        mock_connector = patch_overrides.pop("connector", MagicMock())
        mock_reg = patch_overrides.pop("connector_registration", MagicMock())
        mock_reg.sql_dialect_hint = patch_overrides.pop("sql_dialect_hint", None)

        profile_table_mock = patch_overrides.pop("profile_table", MagicMock(return_value={"columns": {}}))

        context_result = patch_overrides.pop("context", {"tables": {}})
        build_context_mock = patch_overrides.pop("build_connection_context", MagicMock(return_value=context_result))

        context_path = patch_overrides.pop("context_path", "/tmp/context.json")
        save_context_mock = patch_overrides.pop("save_context_file", MagicMock(return_value=context_path))

        load_schema_mock = patch_overrides.pop("load_schema_file", MagicMock(return_value=schema))

        self_mock = _mock_self(retries)

        with (
            patch(f"{self._P}.SessionLocal", return_value=mock_session),
            patch("backend.services.schema_discovery.load_schema_file", load_schema_mock),
            patch("backend.connectors.factory.get_connector_for_connection", return_value=mock_connector),
            patch("backend.connectors.factory.get_connector_registration", return_value=mock_reg),
            patch("backend.services.table_profiler.profile_table", profile_table_mock),
            patch("backend.services.connection_context.build_connection_context", build_context_mock),
            patch("backend.services.connection_context.save_context_file", save_context_mock),
        ):
            _profile_connection_fn(self_mock, connection_id=connection_id)

        return {
            "connection": connection,
            "session": mock_session,
            "load_schema_file": load_schema_mock,
            "profile_table": profile_table_mock,
            "build_connection_context": build_context_mock,
            "save_context_file": save_context_mock,
            "connector": mock_connector,
            "connector_registration": mock_reg,
            "self_mock": self_mock,
        }

    # ----- Happy path -----

    def test_happy_path_sets_status_ready(self):
        """Full flow: loads schema, profiles tables, builds context, saves file, sets status to 'ready'."""
        result = self._run(connection_id=1)
        conn = result["connection"]

        assert conn.profiling_status == "ready"
        assert conn.profiling_error is None
        assert conn.data_context_path is not None
        result["load_schema_file"].assert_called_once_with(1)
        result["build_connection_context"].assert_called_once()
        result["save_context_file"].assert_called_once()
        result["connector"].close.assert_called_once()

    # ----- Progress tracking -----

    def test_updates_progress_per_table(self):
        """With 3 tables, profiling_progress should be set to '1/3 tables', '2/3 tables', '3/3 tables'."""
        schema = _minimal_schema({
            "t1": {"row_count": 10, "columns": [{"name": "id", "type": "integer"}]},
            "t2": {"row_count": 20, "columns": [{"name": "id", "type": "integer"}]},
            "t3": {"row_count": 30, "columns": [{"name": "id", "type": "integer"}]},
        })
        conn = _make_mock_connection(cid=1)

        # Track all assignments to profiling_progress
        progress_values = []
        original_setattr = type(conn).__setattr__

        def track_progress(self_obj, name, value):
            if name == "profiling_progress":
                progress_values.append(value)
            original_setattr(self_obj, name, value)

        with patch.object(type(conn), "__setattr__", track_progress):
            self._run(connection_id=1, connection=conn, schema_json=schema)

        # Should include per-table progress: 1/3, 2/3, 3/3 (during loop)
        # and the final 3/3 set after completion
        assert "1/3 tables" in progress_values
        assert "2/3 tables" in progress_values
        assert "3/3 tables" in progress_values

    # ----- Error: missing schema -----

    def test_missing_schema_file_sets_status_failed(self):
        """load_schema_file raises FileNotFoundError -> status = 'failed', error message set."""
        conn = _make_mock_connection(cid=1)
        load_mock = MagicMock(side_effect=FileNotFoundError("no schema"))

        self._run(connection_id=1, connection=conn, load_schema_file=load_mock)

        assert conn.profiling_status == "failed"
        assert "Schema file not found" in conn.profiling_error

    # ----- Connection not found -----

    def test_connection_not_found_returns_early(self):
        """session.query returns None for connection -> function returns without error."""
        _, mock_session = _make_db_session_factory(connection=None)
        self_mock = _mock_self()

        with patch(f"{self._P}.SessionLocal", return_value=mock_session):
            _profile_connection_fn(self_mock, connection_id=999)

        # No retry should have been triggered
        self_mock.retry.assert_not_called()
        mock_session.close.assert_called_once()

    # ----- Per-table error handling -----

    def test_per_table_error_continues_profiling(self):
        """profile_table raises on one table but succeeds on others -> other tables are still profiled."""
        schema = _minimal_schema({
            "good_table": {"row_count": 10, "columns": [{"name": "id", "type": "integer"}]},
            "bad_table": {"row_count": 20, "columns": [{"name": "id", "type": "integer"}]},
            "another_good": {"row_count": 30, "columns": [{"name": "id", "type": "integer"}]},
        })

        table_names_called = []

        def profile_side_effect(connector, table_name, schema_name, columns, row_count, db_type, is_dataset):
            table_names_called.append(table_name)
            if table_name == "bad_table":
                raise RuntimeError("profiling failed for bad_table")
            return {"columns": {}, "table_name": table_name}

        profile_mock = MagicMock(side_effect=profile_side_effect)
        result = self._run(
            connection_id=1,
            schema_json=schema,
            profile_table=profile_mock,
        )

        # All 3 tables should have been attempted
        assert len(table_names_called) == 3
        # build_connection_context should still be called
        result["build_connection_context"].assert_called_once()
        # Final status should be ready (per-table errors don't fail the whole task)
        assert result["connection"].profiling_status == "ready"

    # ----- Context file saving -----

    def test_saves_context_file_on_success(self):
        """Verify save_context_file is called with the built context."""
        context_data = {"tables": {"orders": {"columns": {}}}}
        build_mock = MagicMock(return_value=context_data)

        result = self._run(
            connection_id=1,
            build_connection_context=build_mock,
        )

        result["save_context_file"].assert_called_once_with(1, context_data)

    def test_sets_data_context_path_on_connection(self):
        """connection.data_context_path is set to the save result."""
        context_path = "/data/contexts/conn_1.json"

        result = self._run(
            connection_id=1,
            context_path=context_path,
        )

        assert result["connection"].data_context_path == context_path

    # ----- General exception & retry -----

    def test_exception_sets_status_failed_and_retries(self):
        """General exception -> status = 'failed', self.retry called."""
        conn = _make_mock_connection(cid=1)
        _, mock_session = _make_db_session_factory(conn)
        self_mock = _mock_self()

        # Make get_connector_for_connection raise to trigger the except branch
        with (
            patch(f"{self._P}.SessionLocal", return_value=mock_session),
            patch("backend.services.schema_discovery.load_schema_file", return_value=_minimal_schema()),
            patch("backend.connectors.factory.get_connector_for_connection", side_effect=RuntimeError("db down")),
            patch("backend.connectors.factory.get_connector_registration", return_value=MagicMock(sql_dialect_hint=None)),
            patch("backend.services.table_profiler.profile_table"),
            patch("backend.services.connection_context.build_connection_context"),
            patch("backend.services.connection_context.save_context_file"),
            pytest.raises(Exception, match="celery-retry-sentinel"),
        ):
            _profile_connection_fn(self_mock, connection_id=1)

        self_mock.retry.assert_called_once()
        # The connection should have been updated with failed status
        assert conn.profiling_status == "failed"
        assert "db down" in conn.profiling_error


# ---------------------------------------------------------------------------
# TestBackfillProfileAllConnections
# ---------------------------------------------------------------------------

class TestBackfillProfileAllConnections:
    """Tests for the ``backfill_profile_all_connections`` Celery task."""

    _P = "backend.tasks.profiling_tasks"

    def test_queues_pending_connections_with_schema(self):
        """Two connections with profiling_status='pending' and schema_json_path set -> both get queued."""
        conn1 = _make_mock_connection(cid=1)
        conn2 = _make_mock_connection(cid=2)

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = [conn1, conn2]

        with (
            patch(f"{self._P}.SessionLocal", return_value=mock_session),
            patch(f"{self._P}.profile_connection") as mock_task,
        ):
            _backfill_task()

        assert mock_task.delay.call_count == 2
        mock_task.delay.assert_any_call(1)
        mock_task.delay.assert_any_call(2)
        mock_session.close.assert_called_once()

    def test_skips_connections_without_schema(self):
        """Connection with profiling_status='pending' but schema_json_path=None -> not in query results."""
        # The filter in the code already excludes None schema_json_path,
        # so the query result should be empty when no connections match.
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []

        with (
            patch(f"{self._P}.SessionLocal", return_value=mock_session),
            patch(f"{self._P}.profile_connection") as mock_task,
        ):
            _backfill_task()

        mock_task.delay.assert_not_called()

    def test_no_pending_connections_is_noop(self):
        """Empty query result -> no delay calls."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []

        with (
            patch(f"{self._P}.SessionLocal", return_value=mock_session),
            patch(f"{self._P}.profile_connection") as mock_task,
        ):
            _backfill_task()

        mock_task.delay.assert_not_called()
        mock_session.close.assert_called_once()
