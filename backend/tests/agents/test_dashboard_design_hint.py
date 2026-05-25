"""Tests for the per-connector dashboard_design_hint injection into the
dashboard agent system prompt."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.plugins.base import ConnectorRegistration


# ---------------------------------------------------------------------------
# ConnectorRegistration field
# ---------------------------------------------------------------------------

def test_connector_registration_default_hint_is_none():
    reg = ConnectorRegistration(
        type_id="t", display_name="t", description="t",
        default_port=1, badge_variant="info", connector_class=type("X", (), {}),
    )
    assert reg.dashboard_design_hint is None


def test_connector_registration_accepts_hint_string():
    reg = ConnectorRegistration(
        type_id="t", display_name="t", description="t",
        default_port=1, badge_variant="info", connector_class=type("X", (), {}),
        dashboard_design_hint="## use this table\nFROM x",
    )
    assert reg.dashboard_design_hint == "## use this table\nFROM x"


# ---------------------------------------------------------------------------
# Prompt builder injection — patches the IO-touching helpers
# ---------------------------------------------------------------------------

def _conn(db_type: str, id_: int = 1, name: str = "n", database: str = "d") -> SimpleNamespace:
    return SimpleNamespace(id=id_, name=name, db_type=db_type, database=database)


def _stub_reg(hint: str | None) -> ConnectorRegistration:
    return ConnectorRegistration(
        type_id="x", display_name="x", description="x",
        default_port=1, badge_variant="info", connector_class=type("X", (), {}),
        dashboard_design_hint=hint,
    )


@pytest.fixture
def _isolated_prompt_builder():
    """Patch the lazy-imported SessionLocal + load_connection_context so the
    prompt builder runs without a database. Returns the build function."""
    from backend.agents.dashboard_agent import prompts

    with patch("backend.database.session.SessionLocal", return_value=MagicMock()), \
         patch("backend.services.connection_context.load_connection_context", return_value=None):
        yield prompts.build_dashboard_agent_prompt


def test_prompt_injects_hint_for_registered_connector(_isolated_prompt_builder):
    with patch("backend.connectors.factory.get_connector_registration",
               return_value=_stub_reg("CUSTOM-HINT-MARKER")):
        prompt = _isolated_prompt_builder(
            available_connections=[1],
            connection_metadata=[_conn("bigquery_ga4")],
        )
    assert "Connector-specific guidance — bigquery_ga4" in prompt
    assert "CUSTOM-HINT-MARKER" in prompt


def test_prompt_omits_hint_when_connector_has_none(_isolated_prompt_builder):
    with patch("backend.connectors.factory.get_connector_registration",
               return_value=_stub_reg(None)):
        prompt = _isolated_prompt_builder(
            available_connections=[1],
            connection_metadata=[_conn("dataset")],
        )
    assert "Connector-specific guidance" not in prompt


def test_prompt_dedupes_hint_for_duplicate_db_types(_isolated_prompt_builder):
    with patch("backend.connectors.factory.get_connector_registration",
               return_value=_stub_reg("MARK")) as get_reg:
        _isolated_prompt_builder(
            available_connections=[1, 2, 3],
            connection_metadata=[
                _conn("bigquery_ga4", id_=1),
                _conn("bigquery_ga4", id_=2),
                _conn("bigquery_ga4", id_=3),
            ],
        )
    # Called once even though there are three bigquery_ga4 connections
    assert get_reg.call_count == 1


def test_prompt_build_does_not_crash_when_hint_lookup_raises(_isolated_prompt_builder):
    with patch("backend.connectors.factory.get_connector_registration",
               side_effect=RuntimeError("boom")):
        # Must not raise — hint injection is wrapped in try/except.
        prompt = _isolated_prompt_builder(
            available_connections=[1],
            connection_metadata=[_conn("bigquery_ga4")],
        )
    assert "Available database connections" in prompt
