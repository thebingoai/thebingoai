"""Tests for agent profile structured field rendering and API."""
import pytest
from unittest.mock import MagicMock, patch


class TestRenderIdentityText:
    def _make_profile(self, **kwargs):
        p = MagicMock()
        p.display_name = kwargs.get('display_name', None)
        p.pronouns = kwargs.get('pronouns', None)
        p.tagline = kwargs.get('tagline', None)
        return p

    def test_renders_name_into_identity_text(self):
        from backend.services.agent_profile_renderer import render_identity_text
        profile = self._make_profile(display_name='Aria')
        result = render_identity_text(profile)
        assert 'Aria' in result

    def test_renders_pronouns(self):
        from backend.services.agent_profile_renderer import render_identity_text
        profile = self._make_profile(display_name='Aria', pronouns='she/her')
        result = render_identity_text(profile)
        assert 'she/her' in result

    def test_renders_tagline(self):
        from backend.services.agent_profile_renderer import render_identity_text
        profile = self._make_profile(display_name='Aria', tagline='Your data ally')
        result = render_identity_text(profile)
        assert 'Your data ally' in result

    def test_defaults_to_bingo_when_no_name(self):
        from backend.services.agent_profile_renderer import render_identity_text
        profile = self._make_profile()
        result = render_identity_text(profile)
        assert 'Bingo' in result


class TestRenderUserContextText:
    def _make_profile(self, **kwargs):
        p = MagicMock()
        p.user_profile = kwargs.get('user_profile', {})
        p.user_narrative = kwargs.get('user_narrative', None)
        p.vocabulary = kwargs.get('vocabulary', [])
        p.sensitivities = kwargs.get('sensitivities', [])
        return p

    def test_renders_profile_fields(self):
        from backend.services.agent_profile_renderer import render_user_context_text
        profile = self._make_profile(user_profile={'address_as': 'Morgan', 'role': 'Head of Growth'})
        result = render_user_context_text(profile)
        assert 'Morgan' in result
        assert 'Head of Growth' in result

    def test_renders_narrative(self):
        from backend.services.agent_profile_renderer import render_user_context_text
        profile = self._make_profile(user_narrative='I prefer direct answers.')
        result = render_user_context_text(profile)
        assert 'I prefer direct answers.' in result

    def test_renders_vocabulary(self):
        from backend.services.agent_profile_renderer import render_user_context_text
        profile = self._make_profile(vocabulary=[{'term': 'enterprise', 'definition': 'Paid accounts'}])
        result = render_user_context_text(profile)
        assert 'enterprise' in result
        assert 'Paid accounts' in result

    def test_renders_sensitivities(self):
        from backend.services.agent_profile_renderer import render_user_context_text
        profile = self._make_profile(sensitivities=["Don't use leverage"])
        result = render_user_context_text(profile)
        assert "Don't use leverage" in result

    def test_renders_multiple_sensitivities(self):
        from backend.services.agent_profile_renderer import render_user_context_text
        profile = self._make_profile(sensitivities=["Don't use leverage", "Avoid jargon"])
        result = render_user_context_text(profile)
        assert "Don't use leverage" in result
        assert "Avoid jargon" in result
        # Verify only one header
        assert result.count("## Sensitivities") == 1

    def test_returns_default_when_all_empty(self):
        from backend.services.agent_profile_renderer import render_user_context_text
        profile = self._make_profile()
        result = render_user_context_text(profile)
        assert isinstance(result, str)
        assert len(result) > 0


class TestProfileRendererPublishSnapshot:
    def test_resolve_uses_published_snapshot_over_draft(self):
        """When published_snapshot exists, resolve() uses snapshot values."""
        from unittest.mock import MagicMock
        from backend.agents.profile_renderer import ProfileRenderer

        mock_user_profile = MagicMock()
        mock_user_profile.user_id = "user-1"
        mock_user_profile.agent_type = "orchestrator"
        mock_user_profile.is_active = True
        mock_user_profile.soul = "DRAFT soul — not yet published"
        mock_user_profile.identity = "DRAFT identity"
        mock_user_profile.user_context = "DRAFT context"
        mock_user_profile.tools = None
        mock_user_profile.agents = None
        mock_user_profile.bootstrap = None
        mock_user_profile.heartbeat = None
        mock_user_profile.guardrails = None
        mock_user_profile.section_locks = {}
        mock_user_profile.version = 5
        mock_user_profile.published_snapshot = {
            "soul": "PUBLISHED soul",
            "identity": "PUBLISHED identity",
            "user_context": "PUBLISHED context",
        }
        mock_user_profile.published_version = 4

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user_profile

        resolved = ProfileRenderer.resolve(mock_db, "orchestrator", user_id="user-1")

        assert resolved.soul == "PUBLISHED soul"
        assert resolved.identity == "PUBLISHED identity"

    def test_resolve_falls_back_to_live_when_no_snapshot(self):
        """When no published_snapshot, resolve() uses the live column values."""
        from unittest.mock import MagicMock
        from backend.agents.profile_renderer import ProfileRenderer

        mock_user_profile = MagicMock()
        mock_user_profile.user_id = "user-1"
        mock_user_profile.agent_type = "orchestrator"
        mock_user_profile.is_active = True
        mock_user_profile.soul = "LIVE soul"
        mock_user_profile.identity = "LIVE identity"
        mock_user_profile.user_context = None
        mock_user_profile.tools = None
        mock_user_profile.agents = None
        mock_user_profile.bootstrap = None
        mock_user_profile.heartbeat = None
        mock_user_profile.guardrails = None
        mock_user_profile.section_locks = {}
        mock_user_profile.version = 1
        mock_user_profile.published_snapshot = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user_profile

        resolved = ProfileRenderer.resolve(mock_db, "orchestrator", user_id="user-1")

        assert resolved.soul == "LIVE soul"


class TestAgentProfileAPI:
    def _make_mock_profile(self):
        p = MagicMock()
        p.display_name = "Bingo"
        p.pronouns = "they/them"
        p.tagline = "Your data, talking back"
        p.avatar_url = None
        p.default_model = "claude-sonnet-4-6"
        p.temperature = 0.4
        p.max_output_tokens = 4096
        p.soul = "# Operating principles\n\nBe helpful."
        p.user_profile = {}
        p.user_narrative = None
        p.vocabulary = []
        p.sensitivities = []
        p.version = 1
        p.published_version = None
        p.published_at = None
        p.identity = "You are Bingo."
        p.user_context = ""
        return p

    @pytest.mark.asyncio
    async def test_get_returns_profile_fields(self):
        from backend.api.agent_profile import get_agent_profile
        mock_profile = self._make_mock_profile()

        with patch('backend.api.agent_profile._get_or_seed_profile', return_value=mock_profile):
            result = await get_agent_profile(db=MagicMock(), user=MagicMock(id="user-1"))

        assert result.display_name == "Bingo"
        assert result.temperature == 0.4

    @pytest.mark.asyncio
    async def test_patch_updates_soul(self):
        from backend.api.agent_profile import patch_agent_profile, AgentProfilePatch

        mock_profile = self._make_mock_profile()
        mock_db = MagicMock()

        with patch('backend.api.agent_profile._get_or_seed_profile', return_value=mock_profile):
            body = AgentProfilePatch(soul="New soul content")
            result = await patch_agent_profile(body=body, db=mock_db, user=MagicMock(id="user-1"))

        assert mock_profile.soul == "New soul content"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_sets_snapshot(self):
        from backend.api.agent_profile import publish_agent_profile

        mock_profile = self._make_mock_profile()
        mock_db = MagicMock()

        with patch('backend.api.agent_profile._get_or_seed_profile', return_value=mock_profile):
            result = await publish_agent_profile(db=mock_db, user=MagicMock(id="user-1"))

        assert result["success"] is True
        assert mock_profile.published_snapshot is not None
        assert mock_profile.published_snapshot["soul"] == mock_profile.soul
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_avatar_upload_rejects_bad_type(self):
        from backend.api.agent_profile import upload_avatar
        from fastapi import HTTPException
        from unittest.mock import patch, AsyncMock

        mock_file = AsyncMock()
        mock_file.content_type = "application/pdf"

        mock_profile = self._make_mock_profile()
        mock_db = MagicMock()

        with patch('backend.api.agent_profile._get_or_seed_profile', return_value=mock_profile):
            with pytest.raises(HTTPException) as exc:
                await upload_avatar(file=mock_file, db=mock_db, user=MagicMock(id="user-1"))
            assert exc.value.status_code == 400
            assert "image type" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_patch_bumps_version_on_first_edit_after_publish(self):
        from backend.api.agent_profile import patch_agent_profile, AgentProfilePatch

        mock_profile = self._make_mock_profile()
        mock_profile.version = 3
        mock_profile.published_version = 3  # currently in sync with publish
        mock_db = MagicMock()

        with patch('backend.api.agent_profile._get_or_seed_profile', return_value=mock_profile):
            body = AgentProfilePatch(soul="Updated")
            await patch_agent_profile(body=body, db=mock_db, user=MagicMock(id="user-1"))

        assert mock_profile.version == 4  # one ahead of published

    @pytest.mark.asyncio
    async def test_patch_does_not_bump_when_already_drafting(self):
        from backend.api.agent_profile import patch_agent_profile, AgentProfilePatch

        mock_profile = self._make_mock_profile()
        mock_profile.version = 4              # already in draft
        mock_profile.published_version = 3    # last publish behind
        mock_db = MagicMock()

        with patch('backend.api.agent_profile._get_or_seed_profile', return_value=mock_profile):
            body = AgentProfilePatch(soul="More edits")
            await patch_agent_profile(body=body, db=mock_db, user=MagicMock(id="user-1"))

        assert mock_profile.version == 4  # unchanged

    @pytest.mark.asyncio
    async def test_patch_does_not_bump_when_never_published(self):
        from backend.api.agent_profile import patch_agent_profile, AgentProfilePatch

        mock_profile = self._make_mock_profile()
        mock_profile.version = 1
        mock_profile.published_version = None  # never published
        mock_db = MagicMock()

        with patch('backend.api.agent_profile._get_or_seed_profile', return_value=mock_profile):
            body = AgentProfilePatch(soul="Pre-publish edits")
            await patch_agent_profile(body=body, db=mock_db, user=MagicMock(id="user-1"))

        assert mock_profile.version == 1  # stays at seeded version

    @pytest.mark.asyncio
    async def test_patch_renders_identity_when_identity_field_changes(self):
        from backend.api.agent_profile import patch_agent_profile, AgentProfilePatch

        mock_profile = self._make_mock_profile()
        mock_db = MagicMock()

        with patch('backend.api.agent_profile._get_or_seed_profile', return_value=mock_profile), \
             patch('backend.services.agent_profile_renderer.render_identity_text', return_value="RENDERED IDENTITY") as mock_render_id, \
             patch('backend.services.agent_profile_renderer.render_user_context_text') as mock_render_ctx:
            body = AgentProfilePatch(display_name="Aria")
            await patch_agent_profile(body=body, db=mock_db, user=MagicMock(id="user-1"))

        mock_render_id.assert_called_once()
        mock_render_ctx.assert_not_called()
        assert mock_profile.identity == "RENDERED IDENTITY"

    @pytest.mark.asyncio
    async def test_patch_renders_user_context_when_context_field_changes(self):
        from backend.api.agent_profile import patch_agent_profile, AgentProfilePatch

        mock_profile = self._make_mock_profile()
        mock_db = MagicMock()

        with patch('backend.api.agent_profile._get_or_seed_profile', return_value=mock_profile), \
             patch('backend.services.agent_profile_renderer.render_identity_text') as mock_render_id, \
             patch('backend.services.agent_profile_renderer.render_user_context_text', return_value="RENDERED CONTEXT") as mock_render_ctx:
            body = AgentProfilePatch(user_narrative="I prefer terse answers.")
            await patch_agent_profile(body=body, db=mock_db, user=MagicMock(id="user-1"))

        mock_render_ctx.assert_called_once()
        mock_render_id.assert_not_called()
        assert mock_profile.user_context == "RENDERED CONTEXT"

    @pytest.mark.asyncio
    async def test_patch_skips_rendering_for_soul_only(self):
        """Soul edits don't trigger identity or user_context re-rendering."""
        from backend.api.agent_profile import patch_agent_profile, AgentProfilePatch

        mock_profile = self._make_mock_profile()
        mock_db = MagicMock()

        with patch('backend.api.agent_profile._get_or_seed_profile', return_value=mock_profile), \
             patch('backend.services.agent_profile_renderer.render_identity_text') as mock_render_id, \
             patch('backend.services.agent_profile_renderer.render_user_context_text') as mock_render_ctx:
            body = AgentProfilePatch(soul="New soul content")
            await patch_agent_profile(body=body, db=mock_db, user=MagicMock(id="user-1"))

        mock_render_id.assert_not_called()
        mock_render_ctx.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_sets_published_version(self):
        from backend.api.agent_profile import publish_agent_profile

        mock_profile = self._make_mock_profile()
        mock_profile.version = 7
        mock_db = MagicMock()

        with patch('backend.api.agent_profile._get_or_seed_profile', return_value=mock_profile):
            result = await publish_agent_profile(db=mock_db, user=MagicMock(id="user-1"))

        assert result["published_version"] == 7
        assert mock_profile.published_version == 7
        assert mock_profile.published_at is not None

    @pytest.mark.asyncio
    async def test_publish_snapshot_includes_structured_fields(self):
        """Snapshot stores all editable fields, not just rendered text columns."""
        from backend.api.agent_profile import publish_agent_profile

        mock_profile = self._make_mock_profile()
        mock_profile.display_name = "Aria"
        mock_profile.temperature = 0.8
        mock_profile.user_profile = {"address_as": "Morgan"}
        mock_profile.vocabulary = [{"term": "MAU", "definition": "monthly active users"}]
        mock_db = MagicMock()

        with patch('backend.api.agent_profile._get_or_seed_profile', return_value=mock_profile):
            await publish_agent_profile(db=mock_db, user=MagicMock(id="user-1"))

        snapshot = mock_profile.published_snapshot
        assert snapshot["display_name"] == "Aria"
        assert snapshot["temperature"] == 0.8
        assert snapshot["user_profile"] == {"address_as": "Morgan"}
        assert snapshot["vocabulary"] == [{"term": "MAU", "definition": "monthly active users"}]
        assert snapshot["soul"] == mock_profile.soul

    @pytest.mark.asyncio
    async def test_reset_reverts_to_snapshot_and_drops_version(self):
        from backend.api.agent_profile import reset_agent_profile

        mock_profile = self._make_mock_profile()
        mock_profile.version = 5
        mock_profile.published_version = 4
        mock_profile.display_name = "DRAFT NAME"
        mock_profile.soul = "DRAFT SOUL"
        mock_profile.published_snapshot = {
            "display_name": "Published Name",
            "soul": "Published soul",
            "temperature": 0.4,
        }
        mock_db = MagicMock()

        with patch('backend.api.agent_profile._get_or_seed_profile', return_value=mock_profile):
            await reset_agent_profile(db=mock_db, user=MagicMock(id="user-1"))

        assert mock_profile.display_name == "Published Name"
        assert mock_profile.soul == "Published soul"
        assert mock_profile.temperature == 0.4
        assert mock_profile.version == 4  # back to published_version
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_rejects_when_never_published(self):
        from backend.api.agent_profile import reset_agent_profile
        from fastapi import HTTPException

        mock_profile = self._make_mock_profile()
        mock_profile.published_version = None
        mock_profile.published_snapshot = None
        mock_db = MagicMock()

        with patch('backend.api.agent_profile._get_or_seed_profile', return_value=mock_profile):
            with pytest.raises(HTTPException) as exc:
                await reset_agent_profile(db=mock_db, user=MagicMock(id="user-1"))
            assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_avatar_upload_rejects_oversize(self):
        from backend.api.agent_profile import upload_avatar
        from fastapi import HTTPException
        from unittest.mock import AsyncMock

        mock_file = AsyncMock()
        mock_file.content_type = "image/png"
        mock_file.read.return_value = b"x" * (2 * 1024 * 1024 + 1)  # 2MB + 1 byte

        mock_profile = self._make_mock_profile()
        mock_db = MagicMock()

        with patch('backend.api.agent_profile._get_or_seed_profile', return_value=mock_profile):
            with pytest.raises(HTTPException) as exc:
                await upload_avatar(file=mock_file, db=mock_db, user=MagicMock(id="user-1"))
            assert exc.value.status_code == 400
            assert "too large" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_avatar_upload_happy_path_returns_data_url(self):
        from backend.api.agent_profile import upload_avatar
        from unittest.mock import AsyncMock

        mock_file = AsyncMock()
        mock_file.content_type = "image/png"
        mock_file.read.return_value = b"\x89PNG\r\n\x1a\n"

        mock_profile = self._make_mock_profile()
        mock_profile.version = 2
        mock_db = MagicMock()

        with patch('backend.api.agent_profile._get_or_seed_profile', return_value=mock_profile):
            result = await upload_avatar(file=mock_file, db=mock_db, user=MagicMock(id="user-1"))

        assert result["avatar_url"].startswith("data:image/png;base64,")
        assert mock_profile.avatar_url == result["avatar_url"]
        assert mock_profile.version == 3
        mock_db.commit.assert_called_once()


class TestGetOrSeedProfile:
    def test_returns_existing_profile(self):
        from backend.api.agent_profile import _get_or_seed_profile

        existing = MagicMock()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing

        result = _get_or_seed_profile(mock_db, "user-1")

        assert result is existing
        mock_db.commit.assert_not_called()

    def test_seeds_when_missing(self):
        from backend.api.agent_profile import _get_or_seed_profile

        seeded = MagicMock()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch('backend.agents.profile_renderer.seed_default_profile', return_value=seeded) as mock_seed:
            result = _get_or_seed_profile(mock_db, "user-1")

        assert result is seeded
        mock_seed.assert_called_once_with(mock_db, "user-1", "orchestrator")
        mock_db.commit.assert_called_once()
