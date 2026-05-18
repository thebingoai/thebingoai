"""Post-verify dashboard widgets returned by the dashboard agent.

Catches structural issues the agent's own prompt should already prevent but
sometimes misses — most importantly, duplicate KPIs for the same metric
across different time-window labels (e.g. "Spend (Last 7 Days)" and
"Spend (7D)").

Pure functions — no DB, no LLM, no side effects. Caller loads widgets and
passes them in.
"""
from __future__ import annotations

import re
from typing import Optional

_WINDOW_ALIASES: list[set[str]] = [
    {"7d", "last 7 days", "past 7 days", "trailing 7 days"},
    {"30d", "last 30 days", "past 30 days", "trailing 30 days"},
    {"90d", "last 90 days", "past 90 days", "trailing 90 days"},
    {"ytd", "year to date", "year-to-date"},
    {"yesterday"},
]

_PAREN_SUFFIX = re.compile(r"\s*\(([^)]+)\)\s*$")

MAX_KPIS = 4
MAX_TOTAL_WIDGETS = 14


def _canonical_window(label: str) -> Optional[str]:
    norm = label.strip().lower()
    for group in _WINDOW_ALIASES:
        if norm in group:
            return sorted(group)[0]
    return None


def _strip_window_suffix(title: str) -> tuple[str, Optional[str]]:
    m = _PAREN_SUFFIX.search(title or "")
    if not m:
        return (title or "", None)
    window = _canonical_window(m.group(1))
    if window is None:
        return (title or "", None)
    base = _PAREN_SUFFIX.sub("", title).strip()
    return (base, window)


def verify_dashboard_widgets(widgets: list[dict]) -> list[str]:
    """Return human-readable violation strings; empty list = clean."""
    violations: list[str] = []

    kpis = [w for w in widgets if (w.get("widget") or {}).get("type") == "kpi"]
    if len(kpis) > MAX_KPIS:
        violations.append(
            f"KPI count = {len(kpis)} — must be 3 or 4. Remove the extras."
        )
    if len(widgets) > MAX_TOTAL_WIDGETS:
        violations.append(
            f"Total widget count = {len(widgets)} — must be ≤ {MAX_TOTAL_WIDGETS}."
        )

    seen_titles: dict[str, list[str]] = {}
    seen_display: dict[str, str] = {}
    for w in kpis:
        config = (w.get("widget") or {}).get("config") or {}
        title = config.get("title") or ""
        base, _window = _strip_window_suffix(title)
        key = base.strip().lower()
        if not key:
            continue
        seen_titles.setdefault(key, []).append(title)
        seen_display.setdefault(key, base.strip())

    for key, titles in seen_titles.items():
        if len(titles) > 1:
            display = seen_display.get(key, key)
            violations.append(
                f"Duplicate KPI metric '{display}' appears in {len(titles)} widgets: {titles}. "
                f"Each metric must appear in at most one KPI. Use the filter bar's "
                f"dateRangeDefault for window switching."
            )

    return violations
