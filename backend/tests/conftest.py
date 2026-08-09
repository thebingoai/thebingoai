import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database.base import Base
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.dashboard import Dashboard


# ── known failures ──────────────────────────────────────────────────────────

_KNOWN_FAILURES = Path(__file__).with_name("known_failures.txt")


def pytest_collection_modifyitems(items):
    """Mark the pre-existing failures xfail so CI can gate on *new* ones.

    The suite is not green and fixing it is separate work. Without this, CI
    would be red on every PR and would therefore tell nobody anything. With it,
    red means a test that used to pass has stopped — which is the only signal
    worth blocking a merge on.

    Non-strict on purpose: fixing a listed test reports XPASS rather than
    breaking everyone else's build. Delete its line when you fix it.
    """
    if not _KNOWN_FAILURES.exists():
        return
    known = {
        line.strip()
        for line in _KNOWN_FAILURES.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    if not known:
        return
    for item in items:
        if item.nodeid in known:
            item.add_marker(
                pytest.mark.xfail(reason="listed in known_failures.txt", strict=False)
            )


@pytest.fixture(scope="session")
def test_engine():
    url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://thebingo_user:thebingo_password@postgres:5432/thebingo_test",
    )
    engine = create_engine(url, future=True)
    try:
        with engine.connect():
            pass
    except OperationalError as e:
        # Skip rather than error: the default suite must stay runnable without a
        # provisioned test database (CI, fresh clone). See the module docstring of
        # test_session_lifecycle.py for the setup these tests need.
        pytest.skip(f"no test database at {url}: {e}")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(test_engine):
    Session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    session = Session()
    try:
        yield session
        session.rollback()
    finally:
        session.close()


@pytest.fixture
def sample_user(db_session):
    u = User(
        id=str(uuid.uuid4()),
        email=f"user-{uuid.uuid4()}@example.com",
        auth_provider="sso",
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def other_user(db_session):
    u = User(
        id=str(uuid.uuid4()),
        email=f"other-{uuid.uuid4()}@example.com",
        auth_provider="sso",
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def sample_dashboard(db_session, sample_user):
    d = Dashboard(
        user_id=sample_user.id,
        title="Test dashboard",
        widgets=[],
    )
    db_session.add(d)
    db_session.commit()
    db_session.refresh(d)
    return d


@pytest.fixture
def authenticated_client(db_session, sample_user):
    """TestClient with get_current_user + get_db overridden to the sample_user / db_session.
    Also sets a default Authorization header so endpoints that read the raw header see something."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: sample_user
    try:
        with TestClient(app) as client:
            client.headers.update({"Authorization": "Bearer test-token"})
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def anonymous_client(db_session):
    """TestClient with NO auth override and NO Authorization header — the only
    honest way to prove the public endpoint needs no identity."""
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
