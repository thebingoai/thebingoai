"""Unit tests for dashboard widget post-verifier.

Covers duplicate-metric detection across canonical window labels,
KPI count cap, and non-window parentheticals.
"""
from backend.agents.orchestrator.dashboard_widget_verifier import (
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


def test_five_distinct_kpis_flags_count_not_dup():
    widgets = [
        _kpi("Spend"),
        _kpi("Impressions"),
        _kpi("Clicks"),
        _kpi("CTR"),
        _kpi("CPC"),
    ]
    violations = verify_dashboard_widgets(widgets)
    assert any("KPI count = 5" in v for v in violations), violations
    assert not any("Duplicate KPI metric" in v for v in violations), violations


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


def test_total_widget_count_cap():
    widgets = [_kpi(f"M{i}") for i in range(3)] + [_chart() for _ in range(13)]
    violations = verify_dashboard_widgets(widgets)
    assert any("Total widget count = 16" in v for v in violations), violations


def test_yesterday_alias_flagged():
    widgets = [
        _kpi("Spend (Yesterday)"),
        _kpi("Spend (yesterday)"),
    ]
    violations = verify_dashboard_widgets(widgets)
    assert any("Duplicate KPI metric 'Spend'" in v for v in violations), violations
