"""Tests for backend.config.feature_flags (Phase 0 — preflight)."""
import json
import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, JSON
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import JSONB

from backend.database.base import Base
from backend.models.organization import Organization
from backend.config.feature_flags import (
    FLAG_DISABLED,
    KNOWN_FLAGS,
    FlagDisabled,
    enabled,
    requires_flag,
    set_flag,
)


# ---------------------------------------------------------------------------
# SQLite in-memory DB (mirrors test_database.py pattern)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def sqlite_session():
    engine = create_engine("sqlite:///:memory:")
    # SQLite doesn't know JSONB; downcast for test compatibility.
    # Also clear server_default to avoid PG-specific syntax (e.g. ::jsonb casts).
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
                col.server_default = None
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def org(sqlite_session):
    o = Organization(id="org-test-1", name="Test Org", feature_flags={})
    sqlite_session.add(o)
    sqlite_session.commit()
    return o


class _NoCloseSessionFactory:
    """Callable that returns a context-manager wrapping a test session without closing it."""

    def __init__(self, session):
        self._session = session

    def __call__(self):
        return self

    def __enter__(self):
        return self._session

    def __exit__(self, *args):
        return False  # don't swallow exceptions, don't close


def _redis_mock(cache_data=None) -> MagicMock:
    """Build a sync Redis mock. Supply `cache_data` dict for a cache hit, else cache miss."""
    m = MagicMock()
    m.get.return_value = json.dumps(cache_data) if cache_data is not None else None
    return m


# ---------------------------------------------------------------------------
# enabled()
# ---------------------------------------------------------------------------

class TestEnabled:
    def test_missing_flag_returns_false_default(self, sqlite_session, org):
        with (
            patch("backend.config.feature_flags._get_redis", return_value=_redis_mock()),
            patch("backend.database.session.SessionLocal", new=_NoCloseSessionFactory(sqlite_session)),
        ):
            assert enabled(org.id, "missing_flag") is False

    def test_missing_flag_respects_custom_default(self, sqlite_session, org):
        with (
            patch("backend.config.feature_flags._get_redis", return_value=_redis_mock()),
            patch("backend.database.session.SessionLocal", new=_NoCloseSessionFactory(sqlite_session)),
        ):
            assert enabled(org.id, "missing_flag", default=True) is True

    def test_bool_flag_read_from_db_on_cache_miss(self, sqlite_session, org):
        org.feature_flags = {"shiny_feature": True}
        sqlite_session.commit()
        redis_m = _redis_mock()  # cache miss

        with (
            patch("backend.config.feature_flags._get_redis", return_value=redis_m),
            patch("backend.database.session.SessionLocal", new=_NoCloseSessionFactory(sqlite_session)),
        ):
            result = enabled(org.id, "shiny_feature")

        assert result is True
        redis_m.setex.assert_called_once()  # cache was populated

    def test_cache_hit_skips_db(self):
        redis_m = _redis_mock({"cache_flag": True})

        with patch("backend.config.feature_flags._get_redis", return_value=redis_m):
            result = enabled("any-org", "cache_flag")

        assert result is True
        redis_m.get.assert_called_once()

    def test_integer_truthy(self, sqlite_session, org):
        org.feature_flags = {"int_flag": 1}
        sqlite_session.commit()

        with (
            patch("backend.config.feature_flags._get_redis", return_value=_redis_mock()),
            patch("backend.database.session.SessionLocal", new=_NoCloseSessionFactory(sqlite_session)),
        ):
            assert enabled(org.id, "int_flag") is True

    def test_integer_falsy(self, sqlite_session, org):
        org.feature_flags = {"int_flag": 0}
        sqlite_session.commit()

        with (
            patch("backend.config.feature_flags._get_redis", return_value=_redis_mock()),
            patch("backend.database.session.SessionLocal", new=_NoCloseSessionFactory(sqlite_session)),
        ):
            assert enabled(org.id, "int_flag") is False

    def test_malformed_cache_falls_back_to_db(self, sqlite_session, org):
        redis_m = MagicMock()
        redis_m.get.return_value = "NOT_JSON!!!"
        org.feature_flags = {"real_flag": True}
        sqlite_session.commit()

        with (
            patch("backend.config.feature_flags._get_redis", return_value=redis_m),
            patch("backend.database.session.SessionLocal", new=_NoCloseSessionFactory(sqlite_session)),
        ):
            assert enabled(org.id, "real_flag") is True

    def test_missing_org_returns_default(self, sqlite_session):
        with (
            patch("backend.config.feature_flags._get_redis", return_value=_redis_mock()),
            patch("backend.database.session.SessionLocal", new=_NoCloseSessionFactory(sqlite_session)),
        ):
            assert enabled("ghost-org", "any_flag", default=False) is False


# ---------------------------------------------------------------------------
# set_flag()
# ---------------------------------------------------------------------------

class TestSetFlag:
    def test_updates_postgres_and_invalidates_cache(self, sqlite_session, org):
        redis_m = _redis_mock()

        with (
            patch("backend.config.feature_flags._get_redis", return_value=redis_m),
            patch("backend.database.session.SessionLocal", new=_NoCloseSessionFactory(sqlite_session)),
        ):
            set_flag(org.id, "my_flag", True)

        sqlite_session.refresh(org)
        assert org.feature_flags.get("my_flag") is True
        redis_m.delete.assert_called_once()

    def test_raises_for_unknown_org(self, sqlite_session):
        with (
            patch("backend.config.feature_flags._get_redis", return_value=_redis_mock()),
            patch("backend.database.session.SessionLocal", new=_NoCloseSessionFactory(sqlite_session)),
        ):
            with pytest.raises(LookupError, match="not found"):
                set_flag("nonexistent-org", "flag", True)


# ---------------------------------------------------------------------------
# @requires_flag
# ---------------------------------------------------------------------------

class TestRequiresFlag:
    def test_returns_disabled_sentinel_when_flag_off(self):
        @requires_flag("some_flag")
        def gated(org_id: str) -> str:
            return "ran"

        with patch("backend.config.feature_flags.enabled", return_value=False):
            result = gated("org-1")

        assert result is FLAG_DISABLED
        assert not bool(result)

    def test_calls_through_when_flag_on(self):
        @requires_flag("some_flag")
        def gated(org_id: str) -> str:
            return "ran"

        with patch("backend.config.feature_flags.enabled", return_value=True):
            assert gated("org-1") == "ran"

    def test_custom_disabled_return(self):
        @requires_flag("some_flag", disabled_return=[])
        def gated(org_id: str) -> list:
            return ["data"]

        with patch("backend.config.feature_flags.enabled", return_value=False):
            assert gated("org-1") == []

    def test_org_id_from_kwarg(self):
        @requires_flag("some_flag")
        def gated(*, org_id: str) -> str:
            return "ran"

        with patch("backend.config.feature_flags.enabled", return_value=True):
            assert gated(org_id="org-1") == "ran"

    def test_missing_org_id_raises_type_error(self):
        @requires_flag("some_flag")
        def gated() -> str:
            return "ran"

        with patch("backend.config.feature_flags.enabled", return_value=True):
            with pytest.raises(TypeError, match="org_id"):
                gated()

    def test_custom_org_id_arg_name(self):
        @requires_flag("some_flag", org_id_arg="organization_id")
        def gated(organization_id: str) -> str:
            return "ran"

        with patch("backend.config.feature_flags.enabled", return_value=True):
            assert gated("org-1") == "ran"


# ---------------------------------------------------------------------------
# Known-flag registry canary
# ---------------------------------------------------------------------------

def test_known_flags_registry():
    """Fail loudly if a flag is removed from KNOWN_FLAGS silently."""
    expected = {
        "new_data_plane",
        "new_pipelines",
        "substrate_migration_complete",
        "new_dbt",
        "governance_v0",
        "governance_v1",
        "governance_v2",
    }
    assert KNOWN_FLAGS >= expected, f"Missing from KNOWN_FLAGS: {expected - KNOWN_FLAGS}"


# ---------------------------------------------------------------------------
# FLAG_DISABLED sentinel
# ---------------------------------------------------------------------------

def test_flag_disabled_is_singleton():
    assert FlagDisabled() is FLAG_DISABLED
    assert FlagDisabled() is FlagDisabled()


def test_flag_disabled_is_falsy():
    assert not FLAG_DISABLED
    assert FLAG_DISABLED is not None
    assert repr(FLAG_DISABLED) == "<FlagDisabled>"
