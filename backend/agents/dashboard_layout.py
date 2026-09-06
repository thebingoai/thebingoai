"""Deterministic layout reflow for agent-generated dashboard widgets.

The dashboard agent decides widget positions on a 12-column grid, but LLM
output often leaves rows underfilled or ragged. Instead of patching the
agent's layout, this module rebuilds it: widgets are taken in reading order,
grouped into rows by type, and every row is stretched to span the full grid
width — so horizontal gaps are impossible by construction.

Row rules:
- filter / text / table: always a full-width row (w=12).
- kpi: consecutive KPI cards are split into balanced rows of up to 5, equal widths.
- chart / pivot_table: greedily packed side-by-side while their preferred
  widths fit in 12 columns; each closed row is stretched proportionally to
  exactly 12 and all members get the row's max height.

Section order is enforced: filter bands first, then KPI rows, then the rest.

Pure functions — no DB, no LLM. Mutates the `position` dicts and re-sorts
the list in place into reading order (y, then x) so the persisted array
order matches the visual order — the frontend grid adds widgets
sequentially and depends on it. Idempotent: a well-formed layout passes
through unchanged. Must never raise — a failure here would block dashboard
creation, and any layout is better than no dashboard.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

GRID_COLUMNS = 12

# Width bounds per widget type, aligned with frontend WIDGET_DEFAULTS
# (frontend/types/dashboard.ts). default_w/default_h used when sanitizing
# garbage values.
_TYPE_CONSTRAINTS: dict[str, dict[str, int]] = {
    "kpi": {"min_w": 2, "max_w": 6, "default_w": 3, "default_h": 2},
    "chart": {"min_w": 3, "max_w": 12, "default_w": 6, "default_h": 5},
    "table": {"min_w": 4, "max_w": 12, "default_w": 12, "default_h": 5},
    "pivot_table": {"min_w": 4, "max_w": 12, "default_w": 8, "default_h": 5},
    "text": {"min_w": 2, "max_w": 12, "default_w": 12, "default_h": 1},
    "section": {"min_w": 2, "max_w": 12, "default_w": 12, "default_h": 1},
    "filter": {"min_w": 4, "max_w": 12, "default_w": 12, "default_h": 2},
}
_FALLBACK_CONSTRAINTS = {"min_w": 2, "max_w": 12, "default_w": 6, "default_h": 4}

# Pie/doughnut charts are unreadable at full width — frontend guidance caps
# them at half the grid. The cap is waived for a widget alone in its row:
# filling the row beats the readability guideline there.
_ROUND_CHART_MAX_W = 6

# Types that always get their own full-width row.
_FULL_ROW_TYPES = {"filter", "text", "section", "table"}

# Types packed side-by-side into shared rows.
_PACKABLE_TYPES = {"chart", "pivot_table"}

_MAX_KPIS_PER_ROW = 5


def _widget_type(widget: dict) -> str:
    return (widget.get("widget") or {}).get("type") or ""


def _constraints_for(widget: dict) -> dict[str, int]:
    wtype = _widget_type(widget)
    constraints = dict(_TYPE_CONSTRAINTS.get(wtype, _FALLBACK_CONSTRAINTS))
    if wtype == "chart":
        chart_type = ((widget.get("widget") or {}).get("config") or {}).get("type")
        if chart_type in ("pie", "doughnut"):
            constraints["max_w"] = _ROUND_CHART_MAX_W
    return constraints


def _coerce_int(value, default: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return n if n >= 0 else default


def _sanitize(widgets: list[dict]) -> None:
    """Coerce x/y/w/h to sane ints in place; clamp to grid and type bounds."""
    for w in widgets:
        pos = w.get("position")
        if not isinstance(pos, dict):
            pos = {}
            w["position"] = pos
        c = _constraints_for(w)
        width = _coerce_int(pos.get("w"), c["default_w"])
        width = max(c["min_w"], min(width if width > 0 else c["default_w"], c["max_w"], GRID_COLUMNS))
        height = _coerce_int(pos.get("h"), c["default_h"])
        height = max(1, height if height > 0 else c["default_h"])
        x = _coerce_int(pos.get("x"), 0)
        x = max(0, min(x, GRID_COLUMNS - width))
        y = _coerce_int(pos.get("y"), 0)
        pos["x"], pos["y"], pos["w"], pos["h"] = x, y, width, height


def _section_key(widget: dict) -> int:
    wtype = _widget_type(widget)
    if wtype == "filter":
        return 0
    if wtype == "kpi":
        return 1
    return 2


def _build_rows(ordered: list[dict]) -> list[list[dict]]:
    """Group widgets into rows: full-width singles, KPI chunks, packed charts."""
    rows: list[list[dict]] = []
    current: list[dict] = []  # open chart/pivot row
    current_width = 0

    def close_current():
        nonlocal current, current_width
        if current:
            rows.append(current)
            current = []
            current_width = 0

    kpi_run: list[dict] = []

    def close_kpis():
        nonlocal kpi_run
        # Balanced rows, not five-then-remainder: six KPIs read as 3+3, not as
        # a full row followed by one lone card capped at half the grid.
        n = len(kpi_run)
        if n:
            n_rows = -(-n // _MAX_KPIS_PER_ROW)
            base, extra = divmod(n, n_rows)
            start = 0
            for r in range(n_rows):
                size = base + (1 if r < extra else 0)
                rows.append(kpi_run[start:start + size])
                start += size
        kpi_run = []

    for w in ordered:
        wtype = _widget_type(w)
        if wtype == "kpi":
            close_current()
            kpi_run.append(w)
            continue
        close_kpis()
        if wtype in _PACKABLE_TYPES:
            width = w["position"]["w"]
            if current and current_width + width > GRID_COLUMNS:
                # Squeeze a pair: two charts that each wanted less than the
                # full grid read better side-by-side (shrunk to fit) than
                # stacked as two underfilled rows. Full-width widgets (w=12,
                # e.g. hero time-series) keep their own row.
                can_squeeze = (
                    len(current) == 1
                    and current_width < GRID_COLUMNS
                    and width < GRID_COLUMNS
                )
                if not can_squeeze:
                    close_current()
            current.append(w)
            current_width += width
        else:
            # filter / text / table / unknown → own full-width row
            close_current()
            rows.append([w])
    close_current()
    close_kpis()
    return rows


def _layout_row(row: list[dict], y: int) -> int:
    """Assign x/w/h for one row starting at y; return the row height."""
    types = {_widget_type(w) for w in row}

    if types <= {"kpi"}:
        n = len(row)
        if n == 1:
            row[0]["position"].update(x=0, w=min(6, _constraints_for(row[0])["max_w"]))
        else:
            base, extra = divmod(GRID_COLUMNS, n)
            cursor = 0
            for i, w in enumerate(row):
                width = base + (1 if i < extra else 0)
                w["position"].update(x=cursor, w=width)
                cursor += width
    elif len(row) == 1:
        w = row[0]
        if _widget_type(w) in _FULL_ROW_TYPES or _widget_type(w) in _PACKABLE_TYPES:
            w["position"].update(x=0, w=GRID_COLUMNS)
        else:
            w["position"].update(x=0)
    else:
        # Packed chart/pivot row: stretch or shrink proportionally so widths
        # sum to exactly 12 columns, clamping each widget at its max width
        # (pie cap) / min width and handing any clamped leftover to the others.
        total = sum(w["position"]["w"] for w in row)
        deficit = GRID_COLUMNS - total
        if deficit < 0:
            overflow = -deficit
            mins = [_constraints_for(w)["min_w"] for w in row]
            shares = [overflow * w["position"]["w"] / total for w in row]
            cuts = [int(s) for s in shares]
            remainder = overflow - sum(cuts)
            by_frac = sorted(range(len(row)), key=lambda i: shares[i] - cuts[i], reverse=True)
            for i in by_frac[:remainder]:
                cuts[i] += 1
            shortfall = 0
            for i, w in enumerate(row):
                new_w = w["position"]["w"] - cuts[i]
                if new_w < mins[i]:
                    shortfall += mins[i] - new_w
                    new_w = mins[i]
                w["position"]["w"] = new_w
            while shortfall > 0:
                shrunk = False
                for i, w in enumerate(row):
                    if shortfall <= 0:
                        break
                    if w["position"]["w"] > mins[i]:
                        w["position"]["w"] -= 1
                        shortfall -= 1
                        shrunk = True
                if not shrunk:
                    break  # every widget at min — row stays slightly over
        elif deficit > 0:
            maxes = [min(_constraints_for(w)["max_w"], GRID_COLUMNS) for w in row]
            shares = [deficit * w["position"]["w"] / total for w in row]
            extras = [int(s) for s in shares]
            remainder = deficit - sum(extras)
            by_frac = sorted(range(len(row)), key=lambda i: shares[i] - extras[i], reverse=True)
            for i in by_frac[:remainder]:
                extras[i] += 1
            leftover = 0
            for i, w in enumerate(row):
                new_w = w["position"]["w"] + extras[i]
                if new_w > maxes[i]:
                    leftover += new_w - maxes[i]
                    new_w = maxes[i]
                w["position"]["w"] = new_w
            while leftover > 0:
                grew = False
                for i, w in enumerate(row):
                    if leftover <= 0:
                        break
                    if w["position"]["w"] < maxes[i]:
                        w["position"]["w"] += 1
                        leftover -= 1
                        grew = True
                if not grew:
                    break  # every widget capped — leave the residual gap
        cursor = 0
        for w in row:
            w["position"]["x"] = cursor
            cursor += w["position"]["w"]

    height = max(w["position"]["h"] for w in row)
    for w in row:
        w["position"]["y"] = y
        w["position"]["h"] = height
    return height


def normalize_dashboard_layout(widgets: list[dict]) -> list[dict]:
    """Reflow agent-generated widget positions in place and return the list.

    Passes: sanitize → reading-order sort → section order (filter → KPIs →
    rest) → rebuild rows (full grid width, uniform row height) → assign y
    top-down → sort the list into reading order. Non-position fields are
    untouched.
    """
    if not widgets:
        return widgets
    try:
        _sanitize(widgets)
        order = sorted(
            range(len(widgets)),
            key=lambda i: (widgets[i]["position"]["y"], widgets[i]["position"]["x"], i),
        )
        ordered = sorted((widgets[i] for i in order), key=_section_key)
        rows = _build_rows(ordered)
        y = 0
        for row in rows:
            y += _layout_row(row, y)
        # Reading-order array: the frontend grid adds widgets sequentially and
        # float:false gravity scrambles saved positions when the array order
        # disagrees with the visual order.
        widgets.sort(key=lambda w: (w["position"]["y"], w["position"]["x"]))
    except Exception:
        # Layout normalization is best-effort — never block dashboard creation.
        logger.warning("normalize_dashboard_layout failed; keeping agent layout", exc_info=True)
    return widgets
