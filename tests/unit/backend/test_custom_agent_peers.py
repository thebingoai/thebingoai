"""Tests for custom agent peer functionality."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.base import Base
from backend.models.user import User
from backend.models.custom_agent import CustomAgent
from backend.models.organization import Organization
from backend.models.team import Team


_TABLES = [
    Organization.__table__,
    Team.__table__,
    User.__table__,
    CustomAgent.__table__,
]


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=_TABLES)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def test_user(test_db):
    org = Organization(name="TestOrg")
    test_db.add(org)
    test_db.commit()

    team = Team(org_id=org.id, name="TestTeam")
    test_db.add(team)
    test_db.commit()

    user = User(email="peer-test@example.com", hashed_password="hashed", org_id=org.id)
    test_db.add(user)
    test_db.commit()

    return user, team, test_db


def test_custom_agent_has_autonomous_fields(test_user):
    """CustomAgent model has is_autonomous and schedule fields."""
    user, team, db = test_user
    agent = CustomAgent(
        user_id=user.id,
        team_id=team.id,
        name="My Monitor",
        system_prompt="Monitor stuff",
        tool_keys=["list_tables", "execute_query"],
        is_autonomous=True,
        schedule="0 * * * *",
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    assert agent.is_autonomous is True
    assert agent.schedule == "0 * * * *"


def test_custom_agent_defaults_non_autonomous(test_user):
    """CustomAgent defaults to non-autonomous."""
    user, team, db = test_user
    agent = CustomAgent(
        user_id=user.id,
        team_id=team.id,
        name="Basic Agent",
        system_prompt="Do stuff",
        tool_keys=["list_tables"],
    )
    db.add(agent)
    db.commit()
    assert agent.is_autonomous is False
    assert agent.schedule is None


def test_custom_agent_schedule_nullable(test_user):
    """Autonomous agent can exist without a schedule."""
    user, team, db = test_user
    agent = CustomAgent(
        user_id=user.id,
        team_id=team.id,
        name="Manual Agent",
        system_prompt="Do stuff",
        tool_keys=["list_tables"],
        is_autonomous=True,
        schedule=None,
    )
    db.add(agent)
    db.commit()
    assert agent.is_autonomous is True
    assert agent.schedule is None
