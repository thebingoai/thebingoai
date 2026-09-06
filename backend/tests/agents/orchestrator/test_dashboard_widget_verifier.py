"""Unit tests for dashboard widget post-verifier.

Covers duplicate-metric detection across canonical window labels,
total widget count cap, and non-window parentheticals.
"""
from backend.agents.orchestrator.dashboard_widget_verifier import (
    MAX_TOTAL_WIDGETS,
    verify_dashboard_widgets,
    _canonical_window,
    _strip_window_suffix,
)


def _kpi(title: str) -> dict:
    return {"widget": {"type": "kpi", "config": {"title": title}}}


def _chart(title: str = "Chart") -> dict:
    return {"widget": {"type": "chart", "config": {"title": title}}}


def test_canonical_window_aliases():
    assert _canonical_window("7d") == _canonical_window("Last 7 Days")
    assert _canonical_window("30D") == _canonical_window("last 30 days")
    assert _canonical_window("YTD") == _canonical_window("Year to Date")
    assert _canonical_window("Top 10 Campaigns") is None
    assert _canonical_window("") is None


def test_strip_window_suffix_returns_base_only_for_window_paren():
    base, win = _strip_window_suffix("Spend (Last 7 Days)")
    assert base == "Spend"
    assert win is not None

    base2, win2 = _strip_window_suffix("Spend (Top 10 Campaigns)")
    assert base2 == "Spend (Top 10 Campaigns)"  # non-window parenthetical left intact
    assert win2 is None

    base3, win3 = _strip_window_suffix("Spend")
    assert base3 == "Spend"
    assert win3 is None


def test_duplicate_7d_and_last_7_days_flagged():
    widgets = [
        _kpi("Spend (Last 7 Days)"),
        _kpi("Spend (7D)"),
        _kpi("Impressions (Last 30 Days)"),
    ]
    violations = verify_dashboard_widgets(widgets)
    assert any("Duplicate KPI metric 'Spend'" in v for v in violations), violations


def test_duplicate_30d_and_last_30_days_flagged():
    widgets = [
        _kpi("Spend (Last 30 Days)"),
        _kpi("Spend (30D)"),
    ]
    violations = verify_dashboard_widgets(widgets)
    assert any("Duplicate KPI metric 'Spend'" in v for v in violations), violations


def test_five_distinct_kpis_no_violation():
    widgets = [
        _kpi("Spend"),
        _kpi("Impressions"),
        _kpi("Clicks"),
        _kpi("CTR"),
        _kpi("CPC"),
    ]
    violations = verify_dashboard_widgets(widgets)
    assert violations == [], violations


def test_four_distinct_kpis_no_violation():
    widgets = [
        _kpi("Spend (Last 30 Days)"),
        _kpi("Impressions (Last 30 Days)"),
        _kpi("Clicks (Last 30 Days)"),
        _kpi("CTR (Last 30 Days)"),
    ]
    violations = verify_dashboard_widgets(widgets)
    assert violations == []


def test_non_window_parenthetical_not_flagged():
    widgets = [
        _kpi("Spend (Top 10 Campaigns)"),
        _kpi("Spend (Bottom 10 Campaigns)"),
    ]
    violations = verify_dashboard_widgets(widgets)
    assert violations == []


def test_bare_name_and_windowed_name_collide():
    widgets = [
        _kpi("Spend"),
        _kpi("Spend (Last 7 Days)"),
    ]
    violations = verify_dashboard_widgets(widgets)
    assert any("Duplicate KPI metric 'Spend'" in v for v in violations), violations


def _section(title: str = "Section") -> dict:
    return {"widget": {"type": "section", "config": {"title": title}}}


def test_count_never_violates():
    """The 2026-09-06 ladder lost 3 of 60 dashboards to a model that answered
    "remove exactly 1" by re-submitting the same 16 widgets. The count is a
    target the prompt states, not a gate this verifier enforces."""
    widgets = [_kpi(f"M{i}") for i in range(5)] + [_chart(f"C{i}") for i in range(15)] + [_section() for _ in range(5)]
    assert len(widgets) == MAX_TOTAL_WIDGETS + 10
    assert verify_dashboard_widgets(widgets) == []


def test_cap_boundary_is_accepted():
    widgets = [_chart() for _ in range(MAX_TOTAL_WIDGETS)]
    assert verify_dashboard_widgets(widgets) == []


def test_data_widgets_excludes_headers_and_prose():
    from backend.agents.orchestrator.dashboard_widget_verifier import data_widgets

    text = {"widget": {"type": "text", "config": {"content": "x"}}}
    widgets = [_kpi("M"), _section(), _chart(), text, {"widget": {"type": "filter"}}]
    assert [w["widget"]["type"] for w in data_widgets(widgets)] == ["kpi", "chart", "filter"]


def test_prompt_states_a_target_not_a_gate():
    """One constant feeds both the prompt and the save-time log, so the number
    the agent is told can never drift from the number we measure against. The
    wording must not promise a rejection the code no longer performs."""
    from backend.agents.dashboard_prompt_blocks import (
        DASHBOARD_WIDGET_CONTRACT,
        MAX_TOTAL_WIDGETS as PROMPT_CAP,
    )

    assert PROMPT_CAP is MAX_TOTAL_WIDGETS
    guidance = DASHBOARD_WIDGET_CONTRACT.split("### Widget Count Guidelines")[1]
    assert f"11-{MAX_TOTAL_WIDGETS} data widgets" in guidance
    assert "not counted" in guidance
    assert "HARD cap" not in guidance
    assert "rejected" not in guidance
    assert "{MAX_WIDGETS}" not in DASHBOARD_WIDGET_CONTRACT  # placeholder was substituted
    assert "17" not in guidance  # no competing number


def test_yesterday_alias_flagged():
    widgets = [
        _kpi("Spend (Yesterday)"),
        _kpi("Spend (yesterday)"),
    ]
    violations = verify_dashboard_widgets(widgets)
    assert any("Duplicate KPI metric 'Spend'" in v for v in violations), violations
