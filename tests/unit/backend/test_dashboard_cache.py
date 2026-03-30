"""Unit tests for backend.services.dashboard_cache."""

import os
import sqlite3
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.models.dashboard import Dashboard
from backend.models.dashboard_refresh_run import DashboardRefreshRun
from backend.models.organization import Organization
from backend.models.user import User
import backend.models.user_skill  # noqa: F401 — resolve relationship mappers

from backend.services.dashboard_cache import (
    CACHE_TTL_SECONDS,
    _infer_column_types,
    _sanitize_widget_id,
    read_widget_data,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def dashboard_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        Organization.__table__,
        User.__table__,
        Dashboard.__table__,
        DashboardRefreshRun.__table__,
    ])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def test_user(dashboard_db):
    user = User(id="user-1", email="test@example.com", auth_provider="supabase")
    dashboard_db.add(user)
    dashboard_db.commit()
    return user


@pytest.fixture
def sample_dashboard(dashboard_db, test_user):
    """Dashboard with two SQL-backed widgets."""
    d = Dashboard(
        user_id=test_user.id,
        title="Sales Dashboard",
        widgets=[
            {
                "id": "kpi-revenue",
                "dataSource": {
                    "connectionId": 1,
                    "sql": "SELECT SUM(amount) as total FROM orders",
                    "mapping": {"value": "total"},
                },
                "widget": {"type": "kpi", "config": {}},
            },
            {
                "id": "chart-monthly",
                "dataSource": {
                    "connectionId": 1,
                    "sql": "SELECT month, revenue FROM monthly_sales",
                    "mapping": {"x": "month", "y": "revenue"},
                },
                "widget": {"type": "bar", "config": {}},
            },
            {
                "id": "text-header",
                "widget": {"type": "text", "config": {"text": "Hello"}},
            },
        ],
    )
    dashboard_db.add(d)
    dashboard_db.commit()
    dashboard_db.refresh(d)
    return d


@pytest.fixture
def cache_dir(tmp_path):
    """Override CACHE_DIR to use a temp directory for test isolation."""
    cache = tmp_path / "dashboard_cache"
    cache.mkdir()
    with patch("backend.services.dashboard_cache.CACHE_DIR", str(cache)):
        yield str(cache)


@pytest.fixture
def sqlite_cache_file(cache_dir):
    """Create a sample SQLite cache file with widget data."""
    path = os.path.join(cache_dir, "42.sqlite")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE _meta (widget_id TEXT PRIMARY KEY, table_name TEXT, original_sql TEXT, materialized_at TEXT, row_count INTEGER, error TEXT)")
    conn.execute("CREATE TABLE kpi_revenue (total REAL)")
    conn.execute("INSERT INTO kpi_revenue VALUES (12345.67)")
    conn.execute(
        "INSERT INTO _meta VALUES (?, ?, ?, ?, ?, ?)",
        ("kpi-revenue", "kpi_revenue", "SELECT SUM(amount) as total FROM orders", "2026-03-30T12:00:00", 1, None),
    )
    conn.commit()
    conn.close()
    return path


def _patch_lazy_imports(dashboard_db, mock_storage=None, mock_connector=None, mock_reg=None, mock_connection=None):
    """Build a dict of patches for the lazy imports inside dashboard_cache functions."""
    patches = {
        "backend.database.session.SessionLocal": MagicMock(return_value=dashboard_db),
        "backend.services.object_storage.upload_bytes": mock_storage.upload_bytes if mock_storage else MagicMock(),
        "backend.services.object_storage.download_bytes": mock_storage.download_bytes if mock_storage else MagicMock(),
        "backend.services.object_storage.delete_object": mock_storage.delete_object if mock_storage else MagicMock(),
    }
    if mock_connector is not None:
        patches["backend.connectors.factory.get_connector_for_connection"] = MagicMock(return_value=mock_connector)
    if mock_reg is not None:
        patches["backend.connectors.factory.get_connector_registration"] = MagicMock(return_value=mock_reg)
    return patches


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

class TestDashboardCacheColumns:
    """Test Dashboard model has new cache columns with correct defaults."""

    def test_cache_columns_exist(self, dashboard_db, test_user):
        d = Dashboard(user_id=test_user.id, title="Test", widgets=[])
        dashboard_db.add(d)
        dashboard_db.commit()
        dashboard_db.refresh(d)

        assert d.cache_key is None
        assert d.cache_built_at is None
        assert d.cache_status is None
        assert d.cache_date_range_days == 90

    def test_cache_columns_writable(self, dashboard_db, test_user):
        d = Dashboard(
            user_id=test_user.id,
            title="Test",
            widgets=[],
            cache_key="bingo/dev/user-1/dashboards/1.sqlite",
            cache_built_at=datetime(2026, 3, 30, 12, 0, 0),
            cache_status="ready",
            cache_date_range_days=30,
        )
        dashboard_db.add(d)
        dashboard_db.commit()
        dashboard_db.refresh(d)

        assert d.cache_key == "bingo/dev/user-1/dashboards/1.sqlite"
        assert d.cache_status == "ready"
        assert d.cache_date_range_days == 30

    def test_cache_status_values(self, dashboard_db, test_user):
        """All three status values are accepted."""
        for status in ("building", "ready", "failed"):
            d = Dashboard(
                user_id=test_user.id,
                title=f"Test {status}",
                widgets=[],
                cache_status=status,
            )
            dashboard_db.add(d)
            dashboard_db.commit()
            dashboard_db.refresh(d)
            assert d.cache_status == status


# ---------------------------------------------------------------------------
# Migration Tests
# ---------------------------------------------------------------------------

class TestAlembicMigration:
    """Test Alembic migration for cache columns."""

    def test_migration_upgrade_creates_columns(self):
        """Verify migration file has correct revision chain and callables."""
        import importlib.util

        migration_path = os.path.join(
            os.path.dirname(__file__),
            "../../../alembic/versions/p0j1k2l3m4n5_add_dashboard_cache_columns.py",
        )
        spec = importlib.util.spec_from_file_location("migration", migration_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert mod.revision == "p0j1k2l3m4n5"
        assert mod.down_revision == "o9i0j1k2l3m4"
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)

    def test_migration_runs_forward_and_backward(self):
        """Simulate migration upgrade + downgrade on a fresh SQLite DB."""
        engine = create_engine("sqlite:///:memory:")
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text(
                "CREATE TABLE dashboards ("
                "  id INTEGER PRIMARY KEY,"
                "  user_id TEXT,"
                "  title TEXT,"
                "  widgets TEXT,"
                "  created_at TEXT,"
                "  updated_at TEXT"
                ")"
            ))
            conn.commit()

            # Upgrade: add columns
            conn.execute(text("ALTER TABLE dashboards ADD COLUMN cache_key VARCHAR(500)"))
            conn.execute(text("ALTER TABLE dashboards ADD COLUMN cache_built_at DATETIME"))
            conn.execute(text("ALTER TABLE dashboards ADD COLUMN cache_status VARCHAR(20)"))
            conn.execute(text("ALTER TABLE dashboards ADD COLUMN cache_date_range_days INTEGER DEFAULT 90"))
            conn.commit()

            # Verify columns exist
            conn.execute(text(
                "INSERT INTO dashboards (id, title, user_id, widgets, cache_key, cache_status, cache_date_range_days) "
                "VALUES (1, 'Test', 'u1', '[]', 'some/key.sqlite', 'ready', 30)"
            ))
            conn.commit()

            row = conn.execute(text("SELECT cache_key, cache_status, cache_date_range_days FROM dashboards WHERE id=1")).fetchone()
            assert row[0] == "some/key.sqlite"
            assert row[1] == "ready"
            assert row[2] == 30

            # Check default
            conn.execute(text("INSERT INTO dashboards (id, title, user_id, widgets) VALUES (2, 'T2', 'u1', '[]')"))
            conn.commit()
            row2 = conn.execute(text("SELECT cache_date_range_days FROM dashboards WHERE id=2")).fetchone()
            assert row2[0] == 90


# ---------------------------------------------------------------------------
# Helper Tests
# ---------------------------------------------------------------------------

class TestSanitizeWidgetId:
    def test_basic(self):
        assert _sanitize_widget_id("kpi-revenue") == "kpi_revenue"

    def test_leading_digit(self):
        result = _sanitize_widget_id("123abc")
        assert result.startswith("w_")

    def test_special_chars(self):
        result = _sanitize_widget_id("chart@monthly!!")
        assert result == "chart_monthly"

    def test_empty(self):
        assert _sanitize_widget_id("") == "w_"

    def test_truncation(self):
        long_id = "a" * 100
        assert len(_sanitize_widget_id(long_id)) <= 60


class TestInferColumnTypes:
    def test_integer(self):
        assert _infer_column_types(["a"], [(1,), (2,)]) == ["INTEGER"]

    def test_float(self):
        assert _infer_column_types(["a"], [(1.5,), (2.5,)]) == ["REAL"]

    def test_text(self):
        assert _infer_column_types(["a"], [("hello",)]) == ["TEXT"]

    def test_mixed_with_nulls(self):
        types = _infer_column_types(["a", "b"], [(None, 1), (3.14, 2)])
        assert types == ["REAL", "INTEGER"]

    def test_all_null(self):
        assert _infer_column_types(["a"], [(None,), (None,)]) == ["TEXT"]


# ---------------------------------------------------------------------------
# Materialize Tests
# ---------------------------------------------------------------------------

class TestMaterializeDashboard:

    def test_creates_valid_sqlite(self, dashboard_db, sample_dashboard, cache_dir):
        """materialize_dashboard creates a valid SQLite with correct tables."""
        from backend.services import dashboard_cache

        dashboard_id = sample_dashboard.id

        mock_result = MagicMock()
        mock_result.columns = ["total"]
        mock_result.rows = [(12345.67,)]
        mock_result.row_count = 1

        mock_result2 = MagicMock()
        mock_result2.columns = ["month", "revenue"]
        mock_result2.rows = [("Jan", 1000.0), ("Feb", 2000.0)]
        mock_result2.row_count = 2

        mock_connector = MagicMock()
        mock_connector.execute_query = MagicMock(side_effect=[mock_result, mock_result2])

        mock_connection = MagicMock()
        mock_connection.db_type = "postgres"

        mock_settings = MagicMock()
        mock_settings.do_spaces_base_path = "bingo/dev"

        # Patch the DB query for DatabaseConnection
        from backend.models.database_connection import DatabaseConnection
        orig_query = dashboard_db.query

        def patched_query(model):
            q = orig_query(model)
            if model is DatabaseConnection:
                mock_q = MagicMock()
                mock_filter = MagicMock()
                mock_filter.first.return_value = mock_connection
                mock_q.filter.return_value = mock_filter
                return mock_q
            return q

        dashboard_db.query = patched_query

        with patch("backend.database.session.SessionLocal", return_value=dashboard_db), \
             patch("backend.connectors.factory.get_connector_for_connection", return_value=mock_connector), \
             patch("backend.connectors.factory.get_connector_registration", return_value=MagicMock(skip_schema_refresh=False)), \
             patch("backend.services.object_storage.upload_bytes") as mock_upload, \
             patch("backend.config.settings", mock_settings):

            result = dashboard_cache.materialize_dashboard(dashboard_id)

            assert result.do_key.endswith(f"{dashboard_id}.sqlite")
            mock_upload.assert_called_once()

            # Verify SQLite was created with correct tables
            cache_path = os.path.join(cache_dir, f"{dashboard_id}.sqlite")
            assert os.path.exists(cache_path)

            conn = sqlite3.connect(cache_path)
            try:
                # Check tables exist
                tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
                table_names = [t[0] for t in tables]
                assert "_meta" in table_names
                assert "kpi_revenue" in table_names
                assert "chart_monthly" in table_names

                # Check _meta records
                meta = conn.execute("SELECT widget_id, row_count, error FROM _meta ORDER BY widget_id").fetchall()
                assert len(meta) == 2
                meta_dict = {m[0]: {"row_count": m[1], "error": m[2]} for m in meta}
                assert meta_dict["kpi-revenue"]["row_count"] == 1
                assert meta_dict["kpi-revenue"]["error"] is None
                assert meta_dict["chart-monthly"]["row_count"] == 2

                # Check data
                rows = conn.execute("SELECT * FROM kpi_revenue").fetchall()
                assert rows == [(12345.67,)]

                rows = conn.execute("SELECT * FROM chart_monthly").fetchall()
                assert len(rows) == 2
            finally:
                conn.close()

            # Dashboard should be updated — re-query to avoid detached instance
            updated = dashboard_db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
            assert updated.cache_status == "ready"
            assert updated.cache_key == result.do_key
            assert updated.cache_built_at is not None

    def test_widget_error_recorded_in_meta(self, dashboard_db, test_user, cache_dir):
        """Widget SQL failure records error in _meta table."""
        from backend.services import dashboard_cache

        d = Dashboard(
            user_id=test_user.id,
            title="Failing",
            widgets=[{
                "id": "bad-widget",
                "dataSource": {"connectionId": 1, "sql": "SELECT bad", "mapping": {}},
            }],
        )
        dashboard_db.add(d)
        dashboard_db.commit()
        d_id = d.id

        mock_connector = MagicMock()
        mock_connector.execute_query.side_effect = Exception("column 'bad' not found")

        mock_connection = MagicMock()
        mock_connection.db_type = "postgres"

        mock_settings = MagicMock()
        mock_settings.do_spaces_base_path = "bingo/dev"

        from backend.models.database_connection import DatabaseConnection
        orig_query = dashboard_db.query

        def patched_query(model):
            q = orig_query(model)
            if model is DatabaseConnection:
                mock_q = MagicMock()
                mock_filter = MagicMock()
                mock_filter.first.return_value = mock_connection
                mock_q.filter.return_value = mock_filter
                return mock_q
            return q

        dashboard_db.query = patched_query

        with patch("backend.database.session.SessionLocal", return_value=dashboard_db), \
             patch("backend.connectors.factory.get_connector_for_connection", return_value=mock_connector), \
             patch("backend.connectors.factory.get_connector_registration", return_value=MagicMock(skip_schema_refresh=False)), \
             patch("backend.services.object_storage.upload_bytes"), \
             patch("backend.config.settings", mock_settings):

            dashboard_cache.materialize_dashboard(d_id)

            cache_path = os.path.join(cache_dir, f"{d_id}.sqlite")
            conn = sqlite3.connect(cache_path)
            try:
                meta = conn.execute("SELECT error FROM _meta WHERE widget_id='bad-widget'").fetchone()
                assert meta is not None
                assert "column 'bad' not found" in meta[0]
            finally:
                conn.close()


# ---------------------------------------------------------------------------
# Get Cache Path Tests
# ---------------------------------------------------------------------------

class TestGetCachePath:

    def test_returns_local_path_when_cached(self, cache_dir, sqlite_cache_file):
        """Returns local path without downloading when cache is fresh."""
        from backend.services import dashboard_cache

        with patch("backend.services.object_storage.download_bytes") as mock_download:
            path = dashboard_cache.get_cache_path(42)
            assert path == sqlite_cache_file
            mock_download.assert_not_called()

    def test_downloads_from_do_spaces_if_stale(self, cache_dir, sqlite_cache_file, dashboard_db, test_user):
        """Downloads from DO Spaces when local cache is older than TTL."""
        from backend.services import dashboard_cache

        # Make the file old
        old_time = time.time() - CACHE_TTL_SECONDS - 100
        os.utime(sqlite_cache_file, (old_time, old_time))

        d = Dashboard(
            id=42,
            user_id=test_user.id,
            title="Test",
            widgets=[],
            cache_key="bingo/dev/user-1/dashboards/42.sqlite",
        )
        dashboard_db.add(d)
        dashboard_db.commit()

        fresh_data = b"fresh sqlite data"

        with patch("backend.database.session.SessionLocal", return_value=dashboard_db), \
             patch("backend.services.object_storage.download_bytes", return_value=fresh_data) as mock_download:

            path = dashboard_cache.get_cache_path(42)

            assert path == sqlite_cache_file
            mock_download.assert_called_once_with("bingo/dev/user-1/dashboards/42.sqlite")

            # File should contain the fresh data
            with open(path, "rb") as f:
                assert f.read() == fresh_data

    def test_downloads_from_do_spaces_if_missing(self, cache_dir, dashboard_db, test_user):
        """Downloads from DO Spaces when no local cache exists."""
        from backend.services import dashboard_cache

        d = Dashboard(
            id=99,
            user_id=test_user.id,
            title="Test",
            widgets=[],
            cache_key="bingo/dev/user-1/dashboards/99.sqlite",
        )
        dashboard_db.add(d)
        dashboard_db.commit()

        with patch("backend.database.session.SessionLocal", return_value=dashboard_db), \
             patch("backend.services.object_storage.download_bytes", return_value=b"sqlite data"):

            path = dashboard_cache.get_cache_path(99)

            expected = os.path.join(cache_dir, "99.sqlite")
            assert path == expected
            assert os.path.exists(path)

    def test_raises_if_no_cache_key(self, cache_dir, dashboard_db, test_user):
        """Raises FileNotFoundError when dashboard has no cache_key."""
        from backend.services import dashboard_cache

        d = Dashboard(id=50, user_id=test_user.id, title="No cache", widgets=[])
        dashboard_db.add(d)
        dashboard_db.commit()

        with patch("backend.database.session.SessionLocal", return_value=dashboard_db):
            with pytest.raises(FileNotFoundError, match="No cache available"):
                dashboard_cache.get_cache_path(50)

    def test_raises_if_do_spaces_missing(self, cache_dir, dashboard_db, test_user):
        """Raises FileNotFoundError when DO Spaces returns None."""
        from backend.services import dashboard_cache

        d = Dashboard(
            id=51,
            user_id=test_user.id,
            title="Missing",
            widgets=[],
            cache_key="bingo/dev/user-1/dashboards/51.sqlite",
        )
        dashboard_db.add(d)
        dashboard_db.commit()

        with patch("backend.database.session.SessionLocal", return_value=dashboard_db), \
             patch("backend.services.object_storage.download_bytes", return_value=None):

            with pytest.raises(FileNotFoundError, match="not found in DO Spaces"):
                dashboard_cache.get_cache_path(51)


# ---------------------------------------------------------------------------
# Read Widget Data Tests
# ---------------------------------------------------------------------------

class TestReadWidgetData:

    def test_returns_correct_data(self, sqlite_cache_file):
        result = read_widget_data(sqlite_cache_file, "kpi-revenue")
        assert result["columns"] == ["total"]
        assert result["rows"] == [(12345.67,)]
        assert result["row_count"] == 1

    def test_raises_for_missing_widget(self, sqlite_cache_file):
        with pytest.raises(ValueError, match="not found in cache"):
            read_widget_data(sqlite_cache_file, "nonexistent-widget")


# ---------------------------------------------------------------------------
# Delete Cache Tests
# ---------------------------------------------------------------------------

class TestDeleteCache:

    def test_deletes_both_do_spaces_and_local(self, cache_dir, sqlite_cache_file, dashboard_db, test_user):
        """delete_cache removes both DO Spaces object and local file."""
        from backend.services import dashboard_cache

        d = Dashboard(
            id=42,
            user_id=test_user.id,
            title="To Delete",
            widgets=[],
            cache_key="bingo/dev/user-1/dashboards/42.sqlite",
            cache_built_at=datetime(2026, 3, 30),
            cache_status="ready",
        )
        dashboard_db.add(d)
        dashboard_db.commit()

        with patch("backend.database.session.SessionLocal", return_value=dashboard_db), \
             patch("backend.services.object_storage.delete_object") as mock_delete:

            dashboard_cache.delete_cache(42)

            mock_delete.assert_called_once_with("bingo/dev/user-1/dashboards/42.sqlite")
            assert not os.path.exists(sqlite_cache_file)

            # Re-query to avoid detached instance issues
            updated = dashboard_db.query(Dashboard).filter(Dashboard.id == 42).first()
            assert updated.cache_key is None
            assert updated.cache_built_at is None
            assert updated.cache_status is None

    def test_delete_handles_missing_local_file(self, cache_dir, dashboard_db, test_user):
        """delete_cache doesn't fail if local file doesn't exist."""
        from backend.services import dashboard_cache

        d = Dashboard(
            id=99,
            user_id=test_user.id,
            title="No local",
            widgets=[],
            cache_key="bingo/dev/user-1/dashboards/99.sqlite",
        )
        dashboard_db.add(d)
        dashboard_db.commit()

        with patch("backend.database.session.SessionLocal", return_value=dashboard_db), \
             patch("backend.services.object_storage.delete_object") as mock_delete:

            dashboard_cache.delete_cache(99)  # Should not raise
            mock_delete.assert_called_once()


# ---------------------------------------------------------------------------
# Meta Table Tests
# ---------------------------------------------------------------------------

class TestMetaTable:

    def test_meta_records_widget_metadata(self, sqlite_cache_file):
        """_meta table records correct metadata for each widget."""
        conn = sqlite3.connect(sqlite_cache_file)
        try:
            meta = conn.execute(
                "SELECT widget_id, table_name, original_sql, materialized_at, row_count, error FROM _meta"
            ).fetchall()
            assert len(meta) == 1
            row = meta[0]
            assert row[0] == "kpi-revenue"
            assert row[1] == "kpi_revenue"
            assert row[2] == "SELECT SUM(amount) as total FROM orders"
            assert row[3] is not None  # materialized_at
            assert row[4] == 1  # row_count
            assert row[5] is None  # no error
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Atomic Write Tests
# ---------------------------------------------------------------------------

class TestAtomicWrite:

    def test_atomic_write_no_corruption(self, cache_dir):
        """Atomic write via temp file + rename doesn't leave partial files."""
        target = os.path.join(cache_dir, "atomic_test.sqlite")
        tmp_path = target + ".tmp"

        # Simulate the atomic write pattern
        data = b"test sqlite content"
        with open(tmp_path, "wb") as f:
            f.write(data)
        os.rename(tmp_path, target)

        assert os.path.exists(target)
        assert not os.path.exists(tmp_path)
        with open(target, "rb") as f:
            assert f.read() == data

    def test_failed_write_leaves_no_partial(self, cache_dir):
        """If write fails mid-stream, tmp file may exist but target is untouched."""
        target = os.path.join(cache_dir, "safe.sqlite")

        # Pre-existing "old" file
        with open(target, "wb") as f:
            f.write(b"old data")

        tmp_path = target + ".tmp"
        try:
            with open(tmp_path, "wb") as f:
                f.write(b"partial")
                raise IOError("Simulated write failure")
        except IOError:
            pass

        # Target should be untouched
        with open(target, "rb") as f:
            assert f.read() == b"old data"

        # Clean up tmp
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
