"""Tests for backend.auth.dependencies — get_current_user FastAPI dependency."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.auth.base import AuthUser
from backend.database.base import Base
from backend.models.organization import Organization
from backend.models.user import User
import backend.models.user_skill  # noqa: F401 — resolve relationship mappers

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_db():
    """In-memory SQLite with User table for auth dependency tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        Organization.__table__,
        User.__table__,
    ])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def existing_user(auth_db):
    """Pre-existing user found by sso_id."""
    user = User(id="user-existing", email="existing@example.com", sso_id="sso-123", auth_provider="sso")
    auth_db.add(user)
    auth_db.commit()
    return user


@pytest.fixture
def email_only_user(auth_db):
    """Pre-existing user without sso_id (pre-SSO migration)."""
    user = User(id="user-email", email="migrate@example.com", sso_id=None, auth_provider="supabase")
    auth_db.add(user)
    auth_db.commit()
    return user


def _make_credentials(token="valid-token"):
    """Build a mock HTTPAuthorizationCredentials."""
    creds = MagicMock()
    creds.credentials = token
    return creds


def _make_auth_user(**overrides):
    """Build an AuthUser with sensible defaults."""
    defaults = dict(id="sso-123", email="existing@example.com", is_active=True, is_verified=True)
    defaults.update(overrides)
    return AuthUser(**defaults)


# ---------------------------------------------------------------------------
# TestGetCurrentUser
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_valid_token_existing_user_by_sso_id(self, auth_db, existing_user):
        """Valid token + user found by sso_id -> returns user."""
        from backend.auth.dependencies import get_current_user

        sso_user = _make_auth_user(id="sso-123", email="existing@example.com")
        mock_provider = AsyncMock()
        mock_provider.validate_token.return_value = sso_user

        with patch("backend.auth.dependencies.get_auth_provider", return_value=mock_provider):
            result = await get_current_user(
                credentials=_make_credentials("valid-token"),
                db=auth_db,
            )

        assert result.id == existing_user.id
        assert result.email == "existing@example.com"

    @pytest.mark.asyncio
    async def test_valid_token_auto_creates_new_user(self, auth_db):
        """Valid token + no matching user -> auto-creates a new user."""
        from backend.auth.dependencies import get_current_user

        sso_user = _make_auth_user(id="sso-new", email="new@example.com")
        mock_provider = AsyncMock()
        mock_provider.validate_token.return_value = sso_user

        with patch("backend.auth.dependencies.get_auth_provider", return_value=mock_provider), \
             patch("backend.auth.dependencies.settings") as mock_settings:
            mock_settings.auth_provider = "sso"
            mock_settings.enable_governance = False

            result = await get_current_user(
                credentials=_make_credentials("valid-token"),
                db=auth_db,
            )

        assert result.email == "new@example.com"
        assert result.sso_id == "sso-new"
        # Verify it was persisted
        persisted = auth_db.query(User).filter(User.sso_id == "sso-new").first()
        assert persisted is not None

    @pytest.mark.asyncio
    async def test_valid_token_links_email_only_user(self, auth_db, email_only_user):
        """Valid token + user found by email (no sso_id) -> links SSO id."""
        from backend.auth.dependencies import get_current_user

        sso_user = _make_auth_user(id="sso-linked", email="migrate@example.com")
        mock_provider = AsyncMock()
        mock_provider.validate_token.return_value = sso_user

        with patch("backend.auth.dependencies.get_auth_provider", return_value=mock_provider), \
             patch("backend.auth.dependencies.settings") as mock_settings:
            mock_settings.auth_provider = "sso"

            result = await get_current_user(
                credentials=_make_credentials("valid-token"),
                db=auth_db,
            )

        assert result.id == email_only_user.id
        assert result.sso_id == "sso-linked"
        assert result.auth_provider == "sso"

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self, auth_db):
        """Invalid/expired token -> 401 Unauthorized."""
        from backend.auth.dependencies import get_current_user

        mock_provider = AsyncMock()
        mock_provider.validate_token.return_value = None

        with patch("backend.auth.dependencies.get_auth_provider", return_value=mock_provider):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    credentials=_make_credentials("bad-token"),
                    db=auth_db,
                )

        assert exc_info.value.status_code == 401
        assert "credentials" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_inactive_user_raises_403(self, auth_db):
        """Valid token but is_active=False -> 403 Forbidden."""
        from backend.auth.dependencies import get_current_user

        sso_user = _make_auth_user(is_active=False)
        mock_provider = AsyncMock()
        mock_provider.validate_token.return_value = sso_user

        with patch("backend.auth.dependencies.get_auth_provider", return_value=mock_provider):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    credentials=_make_credentials("token"),
                    db=auth_db,
                )

        assert exc_info.value.status_code == 403
        assert "inactive" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_unverified_email_raises_403(self, auth_db):
        """Valid token but is_verified=False -> 403 Forbidden."""
        from backend.auth.dependencies import get_current_user

        sso_user = _make_auth_user(is_verified=False)
        mock_provider = AsyncMock()
        mock_provider.validate_token.return_value = sso_user

        with patch("backend.auth.dependencies.get_auth_provider", return_value=mock_provider):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    credentials=_make_credentials("token"),
                    db=auth_db,
                )

        assert exc_info.value.status_code == 403
        assert "verified" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_auto_create_with_governance_adds_team_membership(self, auth_db):
        """When governance is enabled, new user gets default org and team membership."""
        from backend.auth.dependencies import get_current_user, DEFAULT_ORG_ID, DEFAULT_TEAM_ID
        from backend.models.team_membership import TeamMembership

        # Create tables needed for governance
        from backend.models.team import Team
        from backend.models.team_membership import TeamMembership as TM
        engine = auth_db.get_bind()
        Team.__table__.create(engine, checkfirst=True)
        TM.__table__.create(engine, checkfirst=True)

        # Pre-create the default org and team to satisfy FK
        org = Organization(id=DEFAULT_ORG_ID, name="Default Org")
        auth_db.add(org)
        auth_db.flush()
        team = Team(id=DEFAULT_TEAM_ID, name="Default Team", org_id=DEFAULT_ORG_ID)
        auth_db.add(team)
        auth_db.commit()

        sso_user = _make_auth_user(id="sso-gov", email="gov@example.com")
        mock_provider = AsyncMock()
        mock_provider.validate_token.return_value = sso_user

        with patch("backend.auth.dependencies.get_auth_provider", return_value=mock_provider), \
             patch("backend.auth.dependencies.settings") as mock_settings:
            mock_settings.auth_provider = "sso"
            mock_settings.enable_governance = True

            result = await get_current_user(
                credentials=_make_credentials("token"),
                db=auth_db,
            )

        assert result.org_id == DEFAULT_ORG_ID
        membership = auth_db.query(TeamMembership).filter(
            TeamMembership.user_id == result.id
        ).first()
        assert membership is not None
        assert membership.team_id == DEFAULT_TEAM_ID
