import os
import sys
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

# Strict mode is what makes the baseline a gate rather than a note. It is off by
# default so a partial local run (-k, a single file) doesn't trip the
# every-entry-was-collected check; CI sets BINGO_STRICT_BASELINE=1.
_STRICT = os.environ.get("BINGO_STRICT_BASELINE") == "1"

_known: dict[str, str | None] = {}   # nodeid -> expected exception type
_observed: dict[str, set[str]] = {}  # nodeid -> exception types actually raised
_unmatched: list[str] = []


def _load_known_failures() -> dict[str, str | None]:
    """Parse `nodeid :: ExceptionType` lines. A bare nodeid means no type recorded."""
    if not _KNOWN_FAILURES.exists():
        return {}
    entries: dict[str, str | None] = {}
    for line in _KNOWN_FAILURES.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        nodeid, sep, exc_type = line.partition(" :: ")
        entries[nodeid.strip()] = exc_type.strip() if sep else None
    return entries


def pytest_collection_modifyitems(items):
    """Mark the pre-existing failures xfail so CI can gate on *new* ones.

    The suite is not green and fixing it is separate work. Without this, CI
    would be red on every PR and would therefore tell nobody anything. With it,
    red means a test that used to pass has stopped — which is the only signal
    worth blocking a merge on.

    Non-strict on purpose: fixing a listed test reports XPASS rather than
    breaking everyone else's build. Delete its line when you fix it.
    """
    _known.update(_load_known_failures())
    if not _known:
        return
    for item in items:
        if item.nodeid in _known:
            item.add_marker(
                pytest.mark.xfail(reason="listed in known_failures.txt", strict=False)
            )
    # A listed test that no longer exists (renamed, deleted) would otherwise sit
    # in the file forever, excusing nothing.
    _unmatched[:] = sorted(_known.keys() - {item.nodeid for item in items})


def pytest_runtest_makereport(item, call):
    """Record what a listed test actually raised.

    Matching on the node ID alone accepts *any* failure at that ID, so a test
    that starts failing for a genuinely new reason slips through the gate.
    Returning None leaves report construction to pytest — this only observes.
    """
    if call.excinfo is not None and item.nodeid in _known:
        _observed.setdefault(item.nodeid, set()).add(call.excinfo.typename)
    return None


# Modules a test must not leave replaced in sys.modules.
_PROTECTED = (
    "backend.config",
    "backend.data_plane.scope",
    "backend.models.pipeline",
    "backend.models.transforms",
    "backend.pipelines.runner",
    "backend.plugins.base",
    "backend.services.data_plane_service",
)


def pytest_collection_finish(session):
    """Fail if a test module left a stub in sys.modules at import time.

    pytest imports every test file during collection, before any test runs, so a
    module-level `sys.modules[...] = MagicMock()` is live while every *other*
    file is imported — silently breaking any of them that import the real
    module. Scope such stubs with `patch.dict(sys.modules, ...)` around the
    import that needs them; see backend/tests/services/test_template_materializer.py.
    """
    # MagicMock raises AttributeError on dunder lookups and a types.ModuleType
    # stub has no __file__ either, so this catches both stub styles.
    leaked = [
        name for name in _PROTECTED
        if name in sys.modules and not getattr(sys.modules[name], "__file__", None)
    ]
    if leaked:
        raise pytest.UsageError(
            "sys.modules stub leaked past collection: " + ", ".join(leaked)
            + " — wrap the install in patch.dict(sys.modules, ...)"
        )


def pytest_sessionfinish(session, exitstatus):
    """Under strict mode, a rotten baseline fails the run."""
    if not _STRICT or not _known:
        return
    problems = [f"listed but never collected (renamed or deleted?): {n}" for n in _unmatched]
    problems += [
        f"no failure type recorded: {n}" for n, exc in sorted(_known.items()) if exc is None
    ]
    problems += [
        f"{n}: recorded {exc}, raised {'/'.join(sorted(_observed[n]))}"
        for n, exc in sorted(_known.items())
        # An empty observed set is XPASS — the test was fixed, which is fine.
        if exc is not None and _observed.get(n) and exc not in _observed[n]
    ]
    if not problems:
        return
    session.exitstatus = 1
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.section("known_failures.txt is out of date", red=True, bold=True)
        for problem in problems:
            reporter.line(f"  {problem}")
        reporter.line("")
        reporter.line("  Fix the test and delete its line. Never edit a line to match a new failure.")


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
