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
    user = User(id="user-1", email="test@example.com", auth_provider="sso")
    dashboard_db.add(user)
    dashboard_db.commit()
    return user
