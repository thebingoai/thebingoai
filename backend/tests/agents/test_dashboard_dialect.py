"""Dashboard agent prompt is locked to BigQuery dialect.

Widget SQL always executes against the DataPlane = BigQuery in enterprise
lockdown. The generator MUST emit BigQuery; Postgres idioms like `::cast`,
`AT TIME ZONE`, `INTERVAL 'N day'`, and `DATE_TRUNC('day', col)` fail at
BigQuery execution. This module locks the contract.
"""
from unittest.mock import patch

import pytest

from backend.agents import profile_defaults
from backend.agents.dashboard_agent.prompts import build_dashboard_agent_prompt
from backend.agents.profile_defaults import (
    BIGQUERY_DIALECT_HINTS,
    DUCKDB_DIALECT_HINTS,
    SQLITE_DIALECT_HINTS,
    _DUCKDB_REQUIRED_TOKENS,
    _dialect_hints_for_org,
    get_default_section,
)


_BQ_REQUIRED_TOKENS = (
    "backticks",
    "CAST(x AS TYPE)",
    "DATE_TRUNC(x, DAY)",
    "INTERVAL N UNIT",
    "TIMESTAMP_TRUNC",
    "DATE_SUB",
    "LOWER(col) LIKE LOWER(pattern)",
)


def test_bigquery_hints_contain_critical_syntax_rules():
    """Smoke-check that a future copy edit doesn't silently drop the rules
    that caused the original bug."""
    for token in _BQ_REQUIRED_TOKENS:
        assert token in BIGQUERY_DIALECT_HINTS, (
            f"BIGQUERY_DIALECT_HINTS missing required syntax rule: {token!r}"
        )


@pytest.mark.parametrize("csv_loaded,bq_loaded", [
    (False, False),
    (True, False),
    (False, True),
    (True, True),
])
def test_dashboard_prompt_always_has_bigquery_hints(csv_loaded, bq_loaded):
    """BQ hints appended regardless of plugin-loaded flags."""
    with patch.object(profile_defaults, "_csv_plugin_loaded", return_value=csv_loaded), \
         patch.object(profile_defaults, "_bigquery_plugin_loaded", return_value=bq_loaded):
        prompt = build_dashboard_agent_prompt(available_connections=[1])
    assert BIGQUERY_DIALECT_HINTS in prompt


def test_dashboard_prompt_never_contains_sqlite_hints():
    """SQLite hints must not leak in even when CSV plugin is reported loaded.

    CSV uploads write to DataPlane (Parquet → BQ in lockdown). SQLite SQL
    against a BQ data plane fails.
    """
    with patch.object(profile_defaults, "_csv_plugin_loaded", return_value=True), \
         patch.object(profile_defaults, "_bigquery_plugin_loaded", return_value=True):
        prompt = build_dashboard_agent_prompt(available_connections=[1])
    assert SQLITE_DIALECT_HINTS not in prompt


def test_get_default_section_dashboard_tools_locks_to_bigquery():
    """Profile-defaults helper returns BQ hints for dashboard_agent (no org / legacy)."""
    with patch.object(profile_defaults, "_csv_plugin_loaded", return_value=True), \
         patch.object(profile_defaults, "_bigquery_plugin_loaded", return_value=False):
        content = get_default_section("dashboard_agent", "tools")
    assert content is not None
    assert BIGQUERY_DIALECT_HINTS in content
    assert SQLITE_DIALECT_HINTS not in content


# --- Phase 3: per-Org dialect flip (GAP-1) ---------------------------------

def test_duckdb_hints_contain_critical_syntax_rules():
    for token in _DUCKDB_REQUIRED_TOKENS:
        assert token in DUCKDB_DIALECT_HINTS, (
            f"DUCKDB_DIALECT_HINTS missing required syntax rule: {token!r}"
        )


def test_hints_flip_to_duckdb_when_flag_on(monkeypatch):
    import backend.config.feature_flags as ff
    monkeypatch.setattr(ff, "enabled", lambda org_id, flag, default=False: flag == "duckdb_widget_serving")
    assert _dialect_hints_for_org("org-1") == DUCKDB_DIALECT_HINTS


def test_hints_stay_bigquery_when_flag_off(monkeypatch):
    import backend.config.feature_flags as ff
    monkeypatch.setattr(ff, "enabled", lambda *a, **k: False)
    assert _dialect_hints_for_org("org-1") == BIGQUERY_DIALECT_HINTS


def test_hints_bigquery_when_no_org():
    assert _dialect_hints_for_org(None) == BIGQUERY_DIALECT_HINTS


def test_get_default_section_flips_to_duckdb_for_migrated_org(monkeypatch):
    import backend.config.feature_flags as ff
    monkeypatch.setattr(ff, "enabled", lambda *a, **k: True)
    content = get_default_section("dashboard_agent", "tools", org_id="org-1")
    assert DUCKDB_DIALECT_HINTS in content
    assert BIGQUERY_DIALECT_HINTS not in content
