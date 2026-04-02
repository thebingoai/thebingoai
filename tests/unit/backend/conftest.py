# Import UserSkill to satisfy SkillReference's relationship() mapper resolution.
# UserSkill uses JSONB (Postgres-only) so we don't create its table in SQLite tests,
# but it must be imported so SQLAlchemy can resolve the 'UserSkill' string reference.
import backend.models.user_skill  # noqa: F401

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.models.organization import Organization
from backend.models.user import User
from backend.models.dashboard import Dashboard
from backend.models.dashboard_refresh_run import DashboardRefreshRun


@pytest.fixture
def dashboard_db():
    """In-memory SQLite with Dashboard, User, DashboardRefreshRun tables."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        Organization.__table__, User.__table__,
        Dashboard.__table__, DashboardRefreshRun.__table__,
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
def sample_schema_json():
    """Minimal schema JSON matching schema_discovery output format."""
    return {
        "connection_id": 1,
        "schemas": {
            "public": {
                "tables": {
                    "orders": {
                        "row_count": 100,
                        "columns": [
                            {"name": "id", "type": "integer", "nullable": False, "primary_key": True},
                            {"name": "region", "type": "varchar", "nullable": True, "primary_key": False},
                            {"name": "amount", "type": "numeric", "nullable": True, "primary_key": False},
                            {"name": "order_date", "type": "date", "nullable": True, "primary_key": False},
                            {"name": "customer_id", "type": "integer", "nullable": True, "primary_key": False},
                        ],
                    },
                    "customers": {
                        "row_count": 50,
                        "columns": [
                            {"name": "id", "type": "integer", "nullable": False, "primary_key": True},
                            {"name": "name", "type": "varchar", "nullable": True, "primary_key": False},
                            {"name": "segment", "type": "varchar", "nullable": True, "primary_key": False},
                        ],
                    },
                },
            },
        },
        "table_names": ["orders", "customers"],
        "relationships": [
            {"from": "orders.customer_id", "to": "customers.id"},
        ],
    }


@pytest.fixture
def sample_data_context():
    """Minimal dashboard data context for filter injection tests."""
    return {
        "sources": {
            "orders": {"connectionId": 1, "table": "public.orders", "columns": ["region", "amount", "order_date"]},
            "payments": {"connectionId": 1, "table": "public.payments", "columns": ["payment_date", "amount"]},
        },
        "dimensions": {
            "region": {"column": "region", "alias": "o.region", "sources": ["orders"], "cardinality": 5},
            "order_date": {"column": "order_date", "alias": "o.order_date", "sources": ["orders"], "type": "date"},
        },
        "baseJoin": {
            "connectionId": 1,
            "from": "orders o",
            "joins": ["LEFT JOIN payments p ON o.id = p.order_id"],
        },
    }


# ---------------------------------------------------------------------------
# Shared utility fixtures (Phase 6b)
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def fake_redis():
    """MagicMock standing in for a Redis client.

    Provides common Redis methods as MagicMock/AsyncMock so tests can
    assert calls without a live Redis instance.
    """
    redis = MagicMock()
    redis.get = MagicMock(return_value=None)
    redis.set = MagicMock(return_value=True)
    redis.delete = MagicMock(return_value=1)
    redis.exists = MagicMock(return_value=0)
    redis.expire = MagicMock(return_value=True)
    redis.pipeline = MagicMock(return_value=MagicMock())
    return redis


@pytest.fixture
def mock_llm_provider():
    """MagicMock mimicking BaseLLMProvider.

    Both ``chat`` and ``chat_stream`` are async mocks so they can be
    awaited in tests that exercise LLM-dependent code paths.
    """
    provider = MagicMock()
    provider.model = "mock-model"
    provider.chat = AsyncMock(return_value="mocked llm response")

    async def _stream(*_args, **_kwargs):
        for token in ["hello", " ", "world"]:
            yield token

    provider.chat_stream = MagicMock(side_effect=_stream)
    return provider


@pytest.fixture
def test_client():
    """FastAPI TestClient with auth and DB dependency overrides.

    The app lifespan is skipped (Qdrant / plugin discovery not needed).
    ``get_current_user`` returns a stub User and ``get_db`` yields
    an in-memory SQLite session.
    """
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from backend.api import routes
    from backend.auth.dependencies import get_current_user
    from backend.database.session import get_db

    # Lightweight app without the full lifespan
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")

    # Stub user for auth
    stub_user = MagicMock()
    stub_user.id = "test-user-id"
    stub_user.email = "test@example.com"
    stub_user.auth_provider = "supabase"

    app.dependency_overrides[get_current_user] = lambda: stub_user

    # In-memory SQLite session for DB
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        Organization.__table__, User.__table__,
        Dashboard.__table__, DashboardRefreshRun.__table__,
    ])
    TestSession = sessionmaker(bind=engine)

    def _override_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_db

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
