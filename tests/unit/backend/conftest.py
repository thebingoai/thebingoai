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
