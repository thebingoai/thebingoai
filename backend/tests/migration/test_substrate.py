"""Unit tests for backend.migration.substrate.

All I/O (database, object_storage, DataPlane) is mocked; no real DB or cloud
connections are required.
"""
from __future__ import annotations

import io
import sqlite3
import tempfile
import os
import uuid
from unittest.mock import MagicMock, patch, call

import pytest

from backend.migration.substrate import (
    migrate_connection,
    rollback_connection,
    widgets_referencing,
    MigrationJournal,
    WidgetPendingManualRewrite,
    MigrationResult,
    RollbackResult,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_sqlite_db(tables: dict[str, list[dict]]) -> bytes:
    """Return bytes of an in-memory SQLite DB with the given tables/rows.

    tables: {table_name: [row_dict, ...]}
    """
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        conn = sqlite3.connect(tmp_path)
        try:
            for table_name, rows in tables.items():
                if not rows:
                    conn.execute(f'CREATE TABLE "{table_name}" (id INTEGER PRIMARY KEY)')
                    continue
                # Derive columns from first row
                cols = list(rows[0].keys())
                col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
                conn.execute(f'CREATE TABLE "{table_name}" ({col_defs})')
                placeholders = ", ".join("?" for _ in cols)
                for row in rows:
                    conn.execute(
                        f'INSERT INTO "{table_name}" VALUES ({placeholders})',
                        [row[c] for c in cols],
                    )
            conn.commit()
        finally:
            conn.close()

        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Common mock builder
# ---------------------------------------------------------------------------

def _make_mock_connection(
    connection_id: int = 1,
    user_id: str = "user-1",
    org_id: str | None = None,
    dataset_table_name: str | None = "legacy/path.sqlite",
    pre_migration_dataset_table_name: str | None = None,
    owner_scope_kind: str = "user",
    owner_scope_id: str = "user-1",
) -> MagicMock:
    conn = MagicMock()
    conn.id = connection_id
    conn.user_id = user_id
    conn.org_id = org_id
    conn.dataset_table_name = dataset_table_name
    conn.pre_migration_dataset_table_name = pre_migration_dataset_table_name
    conn.owner_scope_kind = owner_scope_kind
    conn.owner_scope_id = owner_scope_id
    return conn


def _model_name(model) -> str:
    """Return a reliable name for a model class, regardless of stub naming."""
    # Try __tablename__ first (most reliable for SQLAlchemy stubs and real models)
    tn = getattr(model, "__tablename__", None)
    if tn:
        return tn
    # Fall back to class qualname / name
    return getattr(model, "__qualname__", None) or getattr(model, "__name__", "") or ""


def _make_fresh_db(connection=None, journal=None) -> MagicMock:
    """Return a MagicMock db where:

    - query(DatabaseConnection).filter(...).first() -> connection
    - query(MigrationJournal).filter(...).first() -> journal
    - query(Dashboard).filter(...).all() -> []
    - query(Dashboard).all() -> []

    Routing is done by __tablename__ (reliable for SQLAlchemy models) falling
    back to qualname / name so tests work with both real models and stubs.
    """
    db = MagicMock()

    def _query_side_effect(model):
        mock_qs = MagicMock()
        mock_qs.filter.return_value.first.return_value = None
        mock_qs.filter.return_value.all.return_value = []
        mock_qs.all.return_value = []

        name = _model_name(model)
        if name in ("database_connections", "DatabaseConnection", "_DatabaseConnection") and connection is not None:
            mock_qs.filter.return_value.first.return_value = connection
        elif name in ("migration_journal", "MigrationJournal"):
            mock_qs.filter.return_value.first.return_value = journal

        return mock_qs

    db.query = MagicMock(side_effect=_query_side_effect)
    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDryRun:
    @patch("backend.services.object_storage.download_bytes")
    @patch("backend.services.object_storage.delete_object")
    @patch("backend.services.data_plane_service.get_default_plane")
    def test_dry_run_produces_no_writes(self, mock_get_plane, mock_delete, mock_download):
        """dry_run=True must not call write_parquet, delete_object, or db.commit."""
        blob = make_sqlite_db({"sales": [{"a": str(i), "b": str(i * 2)} for i in range(3)]})

        mock_download.return_value = blob

        mock_plane = MagicMock()
        mock_get_plane.return_value = mock_plane

        connection = _make_mock_connection(dataset_table_name="legacy/sales.sqlite")
        db = _make_fresh_db(connection=connection, journal=None)

        result = migrate_connection(1, dry_run=True, db=db)

        mock_plane.write_parquet.assert_not_called()
        mock_delete.assert_not_called()
        db.commit.assert_not_called()
        assert result.status == "dry_run"
        assert result.tables_migrated == 1
        assert result.rows_migrated == 3


class TestSingleTableMigration:
    @patch("backend.services.object_storage.download_bytes")
    @patch("backend.services.object_storage.delete_object")
    @patch("backend.services.data_plane_service.get_default_plane")
    def test_single_table_migration(self, mock_get_plane, mock_delete, mock_download):
        """Migrating a single-table SQLite blob writes one Parquet and marks journal migrated."""
        rows = [{"id": str(i), "value": f"v{i}"} for i in range(5)]
        blob = make_sqlite_db({"sales": rows})

        mock_download.return_value = blob

        mock_plane = MagicMock()
        mock_get_plane.return_value = mock_plane

        connection = _make_mock_connection(dataset_table_name="legacy/sales.sqlite")
        db = _make_fresh_db(connection=connection, journal=None)

        result = migrate_connection(1, dry_run=False, db=db)

        assert result.status == "migrated"
        assert result.tables_migrated == 1
        assert result.rows_migrated == 5

        # write_parquet called once with table_name == "sales"
        mock_plane.write_parquet.assert_called_once()
        call_args = mock_plane.write_parquet.call_args
        # Positional: (scope, table_name, arrow_table, mode=...)
        assert call_args[0][1] == "sales"

        mock_delete.assert_called_once()
        db.commit.assert_called()


class TestMultiTableMigration:
    @patch("backend.services.object_storage.download_bytes")
    @patch("backend.services.object_storage.delete_object")
    @patch("backend.services.data_plane_service.get_default_plane")
    def test_multi_table_sqlite_migration(self, mock_get_plane, mock_delete, mock_download):
        """3 tables with 10 rows each → tables_migrated=3, rows_migrated=30."""
        tables = {
            name: [{"id": str(i), "x": "val"} for i in range(10)]
            for name in ("campaigns", "ad_groups", "ads")
        }
        blob = make_sqlite_db(tables)

        mock_download.return_value = blob

        mock_plane = MagicMock()
        mock_get_plane.return_value = mock_plane

        connection = _make_mock_connection(dataset_table_name="legacy/multi.sqlite")
        db = _make_fresh_db(connection=connection, journal=None)

        result = migrate_connection(1, dry_run=False, db=db)

        assert result.status == "migrated"
        assert result.tables_migrated == 3
        assert result.rows_migrated == 30
        assert mock_plane.write_parquet.call_count == 3


class TestResumability:
    def test_resumability_skips_migrated(self):
        """Connection with journal.status='migrated' returns status='skipped' immediately."""
        journal = MagicMock(spec=MigrationJournal)
        journal.status = "migrated"
        journal.legacy_blob_path = "legacy/old.sqlite"
        journal.new_dataplane_table = "sales"

        connection = _make_mock_connection()
        db = _make_fresh_db(connection=connection, journal=journal)

        # object_storage must NOT be touched — we patch to detect any call
        with patch("backend.services.object_storage.download_bytes") as mock_download:
            result = migrate_connection(1, dry_run=False, db=db)
            mock_download.assert_not_called()

        assert result.status == "skipped"


class TestWidgetRewrite:
    @patch("backend.services.object_storage.download_bytes")
    @patch("backend.services.object_storage.delete_object")
    @patch("backend.services.data_plane_service.get_default_plane")
    def test_widget_sql_rewrite_success(self, mock_get_plane, mock_delete, mock_download):
        """Widget SQL referencing a legacy table is rewritten after migration."""
        blob = make_sqlite_db({"legacy_table": [{"id": "1", "v": "a"}]})
        mock_download.return_value = blob
        mock_get_plane.return_value = MagicMock()

        connection = _make_mock_connection(
            connection_id=1,
            user_id="user-1",
            dataset_table_name="legacy/blob.sqlite",
        )

        # Dashboard with 1 widget whose SQL references legacy_table
        widget = {
            "id": "w1",
            "dataSource": {
                "connectionId": 1,
                "sql": "SELECT * FROM legacy_table",
            },
        }
        mock_dashboard = MagicMock()
        mock_dashboard.user_id = "user-1"
        mock_dashboard.id = "dash-1"
        mock_dashboard.widgets = [widget]

        db = MagicMock()

        def _query_side_effect(model):
            mock_qs = MagicMock()
            mock_qs.filter.return_value.first.return_value = None
            mock_qs.filter.return_value.all.return_value = []
            mock_qs.all.return_value = []

            name = _model_name(model)
            if name in ("database_connections", "DatabaseConnection", "_DatabaseConnection"):
                mock_qs.filter.return_value.first.return_value = connection
            elif name in ("migration_journal", "MigrationJournal"):
                mock_qs.filter.return_value.first.return_value = None
            elif name in ("dashboards", "Dashboard", "_Dashboard"):
                mock_qs.filter.return_value.all.return_value = [mock_dashboard]
                mock_qs.all.return_value = [mock_dashboard]

            return mock_qs

        db.query = MagicMock(side_effect=_query_side_effect)

        result = migrate_connection(1, dry_run=False, db=db)

        # DataPlane keeps same table names, so no SQL rewrite needed — migration still succeeds
        assert result.status == "migrated"
        assert result.tables_migrated == 1
        assert result.widgets_queued_for_review == 0

    @patch("backend.services.object_storage.download_bytes")
    @patch("backend.services.object_storage.delete_object")
    @patch("backend.services.data_plane_service.get_default_plane")
    def test_widget_unparseable_sql_queued(self, mock_get_plane, mock_delete, mock_download):
        """Widget with unparseable SQL is queued for manual review."""
        blob = make_sqlite_db({"some_table": [{"id": "1"}]})
        mock_download.return_value = blob
        mock_get_plane.return_value = MagicMock()

        connection = _make_mock_connection(
            connection_id=1,
            user_id="user-1",
            dataset_table_name="legacy/blob.sqlite",
        )

        widget = {
            "id": "w2",
            "dataSource": {
                "connectionId": 1,
                "sql": "THIS IS NOT SQL !!!",
            },
        }
        mock_dashboard = MagicMock()
        mock_dashboard.user_id = "user-1"
        mock_dashboard.id = "dash-2"
        mock_dashboard.widgets = [widget]

        db = MagicMock()

        def _query_side_effect(model):
            mock_qs = MagicMock()
            mock_qs.filter.return_value.first.return_value = None
            mock_qs.filter.return_value.all.return_value = []
            mock_qs.all.return_value = []

            name = _model_name(model)
            if name in ("database_connections", "DatabaseConnection", "_DatabaseConnection"):
                mock_qs.filter.return_value.first.return_value = connection
            elif name in ("migration_journal", "MigrationJournal"):
                mock_qs.filter.return_value.first.return_value = None
            elif name in ("dashboards", "Dashboard", "_Dashboard"):
                mock_qs.filter.return_value.all.return_value = [mock_dashboard]
                mock_qs.all.return_value = [mock_dashboard]

            return mock_qs

        db.query = MagicMock(side_effect=_query_side_effect)

        result = migrate_connection(1, dry_run=False, db=db)

        assert result.widgets_queued_for_review == 1
        assert result.status == "widget_review_pending"


class TestRollback:
    def test_rollback_restores_widget_sql(self):
        """rollback_connection with a migrated journal restores widget SQL and returns rolled_back."""
        journal = MagicMock(spec=MigrationJournal)
        journal.status = "migrated"
        journal.widget_rewrites_applied = [
            {"widget_id": "w1", "old_sql": "SELECT * FROM old", "new_sql": "SELECT * FROM new"}
        ]
        journal.pre_migration_dataset_table_name = "old/path.sqlite"

        widget = {
            "id": "w1",
            "dataSource": {"connectionId": 1, "sql": "SELECT * FROM new"},
        }
        mock_dashboard = MagicMock()
        mock_dashboard.user_id = "user-1"
        mock_dashboard.widgets = [widget]

        connection = _make_mock_connection(
            connection_id=1,
            user_id="user-1",
            dataset_table_name=None,
            pre_migration_dataset_table_name="old/path.sqlite",
        )

        db = MagicMock()

        def _query_side_effect(model):
            mock_qs = MagicMock()
            mock_qs.filter.return_value.first.return_value = None
            mock_qs.filter.return_value.all.return_value = []
            mock_qs.all.return_value = []

            name = _model_name(model)
            if name in ("migration_journal", "MigrationJournal"):
                mock_qs.filter.return_value.first.return_value = journal
            elif name in ("database_connections", "DatabaseConnection", "_DatabaseConnection"):
                mock_qs.filter.return_value.first.return_value = connection
            elif name in ("dashboards", "Dashboard", "_Dashboard"):
                mock_qs.filter.return_value.all.return_value = [mock_dashboard]
                mock_qs.all.return_value = [mock_dashboard]

            return mock_qs

        db.query = MagicMock(side_effect=_query_side_effect)

        result = rollback_connection(1, db=db)

        assert result.status == "rolled_back"
        db.commit.assert_called()

    def test_rollback_no_op_when_not_migrated(self):
        """rollback_connection with no journal returns no_op without touching DB."""
        db = MagicMock()

        def _query_side_effect(model):
            mock_qs = MagicMock()
            mock_qs.filter.return_value.first.return_value = None
            mock_qs.filter.return_value.all.return_value = []
            mock_qs.all.return_value = []
            return mock_qs

        db.query = MagicMock(side_effect=_query_side_effect)

        result = rollback_connection(1, db=db)

        assert result.status == "no_op"
        db.commit.assert_not_called()


class TestWidgetsReferencing:
    def test_widgets_referencing_returns_matching_widgets(self):
        """widgets_referencing returns only widgets whose connectionId matches."""
        widget_match = {
            "id": "w1",
            "dataSource": {"connectionId": 42, "sql": "SELECT 1"},
        }
        widget_no_match = {
            "id": "w2",
            "dataSource": {"connectionId": 99, "sql": "SELECT 2"},
        }

        dash = MagicMock()
        dash.id = "dash-1"
        dash.widgets = [widget_match, widget_no_match]

        db = MagicMock()

        def _query_side_effect(model):
            mock_qs = MagicMock()
            mock_qs.all.return_value = [dash]
            mock_qs.filter.return_value.all.return_value = [dash]
            return mock_qs

        db.query = MagicMock(side_effect=_query_side_effect)

        results = widgets_referencing(42, db=db)

        assert len(results) == 1
        assert results[0]["widget_id"] == "w1"
        assert results[0]["sql"] == "SELECT 1"

    def test_widgets_referencing_returns_empty_when_none_match(self):
        """widgets_referencing returns [] when no widget matches the connection_id."""
        widget = {
            "id": "w1",
            "dataSource": {"connectionId": 99, "sql": "SELECT 1"},
        }

        dash = MagicMock()
        dash.id = "dash-1"
        dash.widgets = [widget]

        db = MagicMock()

        def _query_side_effect(model):
            mock_qs = MagicMock()
            mock_qs.all.return_value = [dash]
            return mock_qs

        db.query = MagicMock(side_effect=_query_side_effect)

        results = widgets_referencing(42, db=db)
        assert results == []


# ---------------------------------------------------------------------------
# Phase 4: unique_key from PRAGMA + post-migration template materialise
# ---------------------------------------------------------------------------


def _make_sqlite_blob_with_pk(table: str, pk_col: str, rows: list[dict]) -> bytes:
    """Build a SQLite blob with an explicit PRIMARY KEY column.

    The default `make_sqlite_db` helper writes all columns as TEXT without a
    PRIMARY KEY constraint, which doesn't exercise the PRAGMA-driven unique_key
    branch added in Phase 4.
    """
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        path = tmp.name
    try:
        conn = sqlite3.connect(path)
        try:
            cols = list(rows[0].keys()) if rows else [pk_col]
            col_defs = ", ".join(
                f'"{c}" INTEGER PRIMARY KEY' if c == pk_col else f'"{c}" TEXT'
                for c in cols
            )
            conn.execute(f'CREATE TABLE "{table}" ({col_defs})')
            placeholders = ", ".join("?" for _ in cols)
            for row in rows:
                conn.execute(
                    f'INSERT INTO "{table}" VALUES ({placeholders})',
                    [row[c] for c in cols],
                )
            conn.commit()
        finally:
            conn.close()
        with open(path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


class TestPhase4UniqueKey:
    @patch("backend.services.object_storage.download_bytes")
    @patch("backend.services.object_storage.delete_object")
    @patch("backend.services.data_plane_service.get_default_plane")
    def test_migrate_passes_unique_key_when_pk_present(
        self, mock_get_plane, _mock_delete, mock_download,
    ):
        """SQLite PRAGMA reports a PRIMARY KEY → write_parquet receives unique_key tuple."""
        blob = _make_sqlite_blob_with_pk(
            "accounts", "id",
            [{"id": i, "name": f"a{i}"} for i in range(3)],
        )
        mock_download.return_value = blob
        mock_plane = MagicMock()
        mock_get_plane.return_value = mock_plane

        connection = _make_mock_connection(dataset_table_name="legacy/accounts.sqlite")
        db = _make_fresh_db(connection=connection, journal=None)

        # Stub out post-migration materialiser so this test stays scoped.
        with patch("backend.services.template_materializer.materialize_post_migration",
                   create=True) as _m:
            _m.return_value = ([], [])
            result = migrate_connection(1, dry_run=False, db=db)

        assert result.status == "migrated"
        mock_plane.write_parquet.assert_called_once()
        call_kwargs = mock_plane.write_parquet.call_args.kwargs
        assert call_kwargs.get("mode") == "overwrite"
        assert call_kwargs.get("unique_key") == ("id",)

    @patch("backend.services.object_storage.download_bytes")
    @patch("backend.services.object_storage.delete_object")
    @patch("backend.services.data_plane_service.get_default_plane")
    def test_migrate_passes_no_unique_key_when_no_pk(
        self, mock_get_plane, _mock_delete, mock_download,
    ):
        """Tables without PK fall back to plain overwrite (no dedup)."""
        blob = make_sqlite_db({"events": [{"a": "1", "b": "2"}]})
        mock_download.return_value = blob
        mock_plane = MagicMock()
        mock_get_plane.return_value = mock_plane

        connection = _make_mock_connection(dataset_table_name="legacy/events.sqlite")
        db = _make_fresh_db(connection=connection, journal=None)

        with patch("backend.services.template_materializer.materialize_post_migration",
                   create=True) as _m:
            _m.return_value = ([], [])
            migrate_connection(1, dry_run=False, db=db)

        call_kwargs = mock_plane.write_parquet.call_args.kwargs
        assert call_kwargs.get("mode") == "overwrite"
        assert "unique_key" not in call_kwargs

    @patch("backend.services.object_storage.download_bytes")
    @patch("backend.services.object_storage.delete_object")
    @patch("backend.services.data_plane_service.get_default_plane")
    def test_migrate_calls_materialize_post_migration_on_success(
        self, mock_get_plane, _mock_delete, mock_download,
    ):
        """Successful (non-dry) migration triggers Pipeline + stg_ row creation."""
        blob = _make_sqlite_blob_with_pk(
            "txn", "id", [{"id": 1, "amount": "10"}],
        )
        mock_download.return_value = blob
        mock_get_plane.return_value = MagicMock()

        connection = _make_mock_connection(dataset_table_name="legacy/txn.sqlite")
        db = _make_fresh_db(connection=connection, journal=None)

        with patch("backend.services.template_materializer.materialize_post_migration",
                   create=True) as mock_post:
            mock_post.return_value = ([], [])
            migrate_connection(1, dry_run=False, db=db)

        mock_post.assert_called_once_with(connection, db)

    @patch("backend.services.object_storage.download_bytes")
    @patch("backend.services.object_storage.delete_object")
    @patch("backend.services.data_plane_service.get_default_plane")
    def test_post_migration_failure_does_not_fail_migration(
        self, mock_get_plane, _mock_delete, mock_download,
    ):
        """A crash inside materialize_post_migration is logged but never undoes
        the successful blob → DataPlane write.
        """
        blob = make_sqlite_db({"t": [{"a": "1"}]})
        mock_download.return_value = blob
        mock_get_plane.return_value = MagicMock()

        connection = _make_mock_connection(dataset_table_name="legacy/t.sqlite")
        db = _make_fresh_db(connection=connection, journal=None)

        with patch("backend.services.template_materializer.materialize_post_migration",
                   create=True) as mock_post:
            mock_post.side_effect = RuntimeError("downstream boom")
            result = migrate_connection(1, dry_run=False, db=db)

        assert result.status == "migrated"
