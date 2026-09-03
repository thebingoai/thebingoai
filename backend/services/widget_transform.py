"""Widget Transform — Pure functions to convert QueryResult into widget config dicts."""
import json
from decimal import Decimal
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from backend.connectors.base import QueryResult
import logging

logger = logging.getLogger(__name__)

# Maps period labels to (current_start, previous_start, previous_end) resolver
_DATE_BASED_PERIODS = {"vs yesterday", "vs last week", "vs last month", "vs last quarter", "vs last year"}


def _to_json_safe(value: Any) -> Any:
    """Convert database-native types to JSON-serializable equivalents."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _find_column(col: str, columns: list, field_name: str = "") -> int:
    """Find column index case-insensitively. Raises ValueError with closest match if not found."""
    if col in columns:
        return columns.index(col)
    col_lower = col.lower()
    for i, c in enumerate(columns):
        if c.lower() == col_lower:
            return i
    from difflib import get_close_matches
    lower_cols = [c.lower() for c in columns]
    closest = get_close_matches(col_lower, lower_cols, n=1, cutoff=0.4)
    hint = ""
    if closest:
        original = columns[lower_cols.index(closest[0])]
        hint = f" Did you mean '{original}'?"
    field_info = f" (mapping field: {field_name})" if field_name else ""
    raise ValueError(
        f"Column '{col}' not found in query results{field_info}.{hint} "
        f"Available columns: {columns}"
    )


def _parse_date_value(value: Any) -> Optional[date]:
    """Parse a date from various formats."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except (ValueError, TypeError):
            return None
    return None


def _parse_datetime_value(value: Any) -> Optional[datetime]:
    """Parse a full datetime (time preserved) from various formats."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        for candidate in (value, value.replace(" ", "T")):
            try:
                return datetime.fromisoformat(candidate)
            except (ValueError, TypeError):
                continue
    return None


_DOW_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _bucket_label(value: Any, granularity: str) -> Tuple[Any, Any]:
    """Bucket a raw label value by date granularity for time-series charts.

    Returns ``(sort_key, display_label)``. The sort_key orders buckets
    chronologically (or 0-23 / Mon-Sun / Jan-Dec for "part" granularities);
    the display_label is what the chart renders on the axis.

    Falls back to ``(value, value)`` when the value is not a parseable date
    or the granularity is none/unknown.
    """
    if not granularity or granularity == "none":
        return value, value
    dt = _parse_datetime_value(value)
    if dt is None:
        return value, value
    if granularity == "year":
        return (dt.year,), str(dt.year)
    if granularity == "quarter":
        q = (dt.month - 1) // 3 + 1
        return (dt.year, q), f"{dt.year}-Q{q}"
    if granularity == "month":
        return (dt.year, dt.month), f"{dt.year}-{dt.month:02d}"
    if granularity == "week":
        iso = dt.isocalendar()
        start = dt.date() - timedelta(days=dt.weekday())
        return (iso[0], iso[1]), start.isoformat()
    if granularity == "day":
        return (dt.year, dt.month, dt.day), dt.date().isoformat()
    if granularity == "hour":
        return (dt.year, dt.month, dt.day, dt.hour), f"{dt.date().isoformat()} {dt.hour:02d}:00"
    if granularity == "hour_of_day":
        return (dt.hour,), f"{dt.hour:02d}:00"
    if granularity == "day_of_week":
        return (dt.weekday(),), _DOW_LABELS[dt.weekday()]
    if granularity == "month_of_year":
        return (dt.month,), _MONTH_LABELS[dt.month - 1]
    return value, value


def _period_ranges(period_label: str, reference: date) -> Tuple[date, date, date, date]:
    """Return (current_start, current_end, previous_start, previous_end) for a period label."""
    today = reference
    if period_label == "vs yesterday":
        return today, today, today - timedelta(days=1), today - timedelta(days=1)
    elif period_label == "vs last week":
        # Current week: Monday..Sunday containing today
        current_start = today - timedelta(days=today.weekday())
        current_end = current_start + timedelta(days=6)
        prev_start = current_start - timedelta(weeks=1)
        prev_end = current_start - timedelta(days=1)
        return current_start, current_end, prev_start, prev_end
    elif period_label == "vs last month":
        current_start = today.replace(day=1)
        if today.month == 1:
            prev_start = today.replace(year=today.year - 1, month=12, day=1)
        else:
            prev_start = today.replace(month=today.month - 1, day=1)
        prev_end = current_start - timedelta(days=1)
        return current_start, today, prev_start, prev_end
    elif period_label == "vs last quarter":
        q = (today.month - 1) // 3
        current_start = today.replace(month=q * 3 + 1, day=1)
        if q == 0:
            prev_start = today.replace(year=today.year - 1, month=10, day=1)
        else:
            prev_start = today.replace(month=(q - 1) * 3 + 1, day=1)
        prev_end = current_start - timedelta(days=1)
        return current_start, today, prev_start, prev_end
    elif period_label == "vs last year":
        current_start = today.replace(month=1, day=1)
        prev_start = today.replace(year=today.year - 1, month=1, day=1)
        prev_end = current_start - timedelta(days=1)
        return current_start, today, prev_start, prev_end
    # Fallback — shouldn't be reached for date-based periods
    return today, today, today, today


#: Every method _aggregate_values distinguishes. Anything else takes its trailing
#: "first" branch, so the KPI paths that accept stored / LLM input check here.
KPI_AGGREGATIONS = frozenset(
    {"sum", "avg", "count", "countDistinct", "min", "max", "first", "last"}
)


def _aggregate_values(values: List[Any], aggregation: str) -> Optional[float]:
    """Aggregate a list of values using the given method."""
    if not values:
        return None
    if aggregation == "sum":
        numeric = [v for v in values if isinstance(v, (int, float))]
        return sum(numeric) if numeric else None
    elif aggregation == "avg":
        numeric = [v for v in values if isinstance(v, (int, float))]
        return round(sum(numeric) / len(numeric), 2) if numeric else None
    elif aggregation == "count":
        return float(len(values))
    elif aggregation == "countDistinct":
        # JSON / JSONB / STRUCT / array cells arrive as dict or list, which are
        # unhashable — set() would raise TypeError and surface as a 500 on the
        # serve path (or burn an LLM SQL-fix round on the bake path) for SQL
        # that is perfectly valid. Key those by canonical text so duplicates
        # still collapse — tagged by kind, so a dict never shares a key with a
        # string column holding the same JSON text.
        return float(len({
            (True, json.dumps(v, sort_keys=True, default=str))
            if isinstance(v, (dict, list)) else (False, v)
            for v in values if v is not None
        }))
    elif aggregation == "min":
        numeric = [v for v in values if isinstance(v, (int, float))]
        return min(numeric) if numeric else None
    elif aggregation == "max":
        numeric = [v for v in values if isinstance(v, (int, float))]
        return max(numeric) if numeric else None
    elif aggregation == "last":
        return values[-1]
    else:  # "first" or unrecognized
        return values[0]


def _transform_timeline(result: QueryResult, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Transform QueryResult into timeline widget config data.

    Mapping keys:
      - labelColumn: row-label dimension (required)
      - startColumn: start-time date column (required)
      - endColumn: end-time date column (required)
      - barLabelColumn: optional per-bar label dimension
      - tooltipColumn: optional extra tooltip dimension

    Returns ``{"data": {"rows": [{rowLabel, barLabel, start, end, tooltip}, ...]}}``
    with dates emitted as ISO strings. The frontend timeline renderer reads the
    raw start/end values and positions bars on a shared time axis.
    """
    row_col = mapping.get("labelColumn")
    start_col = mapping.get("startColumn")
    end_col = mapping.get("endColumn")
    bar_col = mapping.get("barLabelColumn")
    tip_col = mapping.get("tooltipColumn")

    if not (row_col and start_col and end_col) or not result.rows:
        return {"data": {"rows": []}}

    row_idx = _find_column(row_col, result.columns, "labelColumn")
    start_idx = _find_column(start_col, result.columns, "startColumn")
    end_idx = _find_column(end_col, result.columns, "endColumn")
    bar_idx = _find_column(bar_col, result.columns, "barLabelColumn") if bar_col else None
    tip_idx = _find_column(tip_col, result.columns, "tooltipColumn") if tip_col else None

    rows_out: List[Dict[str, Any]] = []
    for row in result.rows:
        rows_out.append({
            "rowLabel": _to_json_safe(row[row_idx]),
            "barLabel": _to_json_safe(row[bar_idx]) if bar_idx is not None else None,
            "start": _to_json_safe(row[start_idx]),
            "end": _to_json_safe(row[end_idx]),
            "tooltip": _to_json_safe(row[tip_idx]) if tip_idx is not None else None,
        })
    return {"data": {"rows": rows_out}}


# Data Studio caps scatter/bubble charts at 1000 points; mirror that.
_MAX_SCATTER_POINTS = 1000


def transform_chart(result: QueryResult, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Transform QueryResult into chart widget config data.

    Mapping keys:
      - labelColumn: dimension column (x-axis labels / pie slices)
      - datasetColumns: list of {column, label, aggregation?, seriesType?, ...} dicts
      - xMetricColumn / yMetricColumn: scatter via dedicated x+y metric columns
      - xAggregation / yAggregation: aggregation for scatter metric columns
      - chartType: legacy hint for (X)/(Y) label-based scatter (fallback only)
      - options: dict with missingData, numberOfPoints, stacked, etc.

    Returns dict suitable for widget.config (merged with existing chart-level fields).
    """
    label_col = mapping.get("labelColumn")
    dataset_cols = mapping.get("datasetColumns", [])
    x_metric_col = mapping.get("xMetricColumn")
    y_metric_col = mapping.get("yMetricColumn")
    chart_type = mapping.get("chartType", "")
    opts: Dict[str, Any] = mapping.get("options") or {}

    # Timeline charts need a per-row {start, end} shape, not labels/datasets.
    if chart_type == "timeline":
        return _transform_timeline(result, mapping)

    _PASSTHROUGH_KEYS = {
        "backgroundColor", "borderColor", "borderWidth", "fill", "tension", "pointRadius",
        "seriesType", "lineWeight", "lineStyle", "showPoints", "stepped", "gradient",
        "cumulative", "showDataLabels", "yAxisID", "trendline",
    }

    empty: Dict[str, Any] = {"data": {"labels": [], "datasets": []}}

    # Ungrouped scatter/bubble series name — meaningful in tooltips ("y vs x").
    xy_label = f"{y_metric_col} vs {x_metric_col}" if x_metric_col and y_metric_col else "Scatter"

    # Guard: no rows → return empty structure preserving dataset labels
    if not result.rows:
        if x_metric_col and y_metric_col:
            return {"data": {"labels": [], "datasets": [{"label": xy_label, "data": []}]}}
        return {"data": {"labels": [], "datasets": [
            {"label": ds.get("label") or ds["column"], "data": []} for ds in dataset_cols
        ]}}

    # ── SCATTER: dedicated x+y metric columns → {x, y} point objects ─────────
    # Optional: labelColumn groups points into one dataset (color) per value;
    # sizeMetricColumn adds `r` per point (bubble chart). Both raw-path only.
    if x_metric_col and y_metric_col:
        x_idx = _find_column(x_metric_col, result.columns, "xMetricColumn")
        y_idx = _find_column(y_metric_col, result.columns, "yMetricColumn")
        y_agg = mapping.get("yAggregation") or "none"
        size_col = mapping.get("sizeMetricColumn")
        size_idx = _find_column(size_col, result.columns, "sizeMetricColumn") if size_col else None

        if y_agg and y_agg != "none":
            # Group by X value, aggregate Y per group
            order: List[Any] = []
            x_groups: Dict[Any, List[Any]] = {}
            for row in result.rows:
                x_val = _to_json_safe(row[x_idx])
                y_val = _to_json_safe(row[y_idx])
                if x_val not in x_groups:
                    x_groups[x_val] = []
                    order.append(x_val)
                x_groups[x_val].append(y_val)
            points = [
                {"x": x, "y": _aggregate_values(x_groups[x], y_agg)}
                for x in order
            ]
            return {"data": {"labels": [], "datasets": [{"label": xy_label, "data": points}]}}

        def _point(row: Any) -> Dict[str, Any]:
            p = {"x": _to_json_safe(row[x_idx]), "y": _to_json_safe(row[y_idx])}
            if size_idx is not None:
                p["r"] = _to_json_safe(row[size_idx])
            return p

        def _cap(pts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            # Data Studio parity: max 1000 points per series — even downsample.
            if len(pts) <= _MAX_SCATTER_POINTS:
                return pts
            step = -(-len(pts) // _MAX_SCATTER_POINTS)  # ceil division
            return pts[::step]

        if label_col:
            group_idx = _find_column(label_col, result.columns, "labelColumn")
            groups: Dict[str, List[Dict[str, Any]]] = {}
            for row in result.rows:
                groups.setdefault(str(_to_json_safe(row[group_idx])), []).append(_point(row))
            return {"data": {"labels": [], "datasets": [
                {"label": gk, "data": _cap(gpts)} for gk, gpts in groups.items()
            ]}}

        points = _cap([_point(row) for row in result.rows])
        return {"data": {"labels": [], "datasets": [{"label": xy_label, "data": points}]}}

    # ── STANDARD: dimension + metric columns ──────────────────────────────────
    if not label_col:
        return empty

    label_idx = _find_column(label_col, result.columns, "labelColumn")

    if not dataset_cols:
        return empty

    # Legacy scatter: (X)/(Y) label-hint detection grouped by labelColumn
    if chart_type == "scatter" and len(dataset_cols) >= 2:
        col0_label = (dataset_cols[0].get("label") or "").upper()
        col1_label = (dataset_cols[1].get("label") or "").upper()
        if "(X)" in col0_label and "(Y)" in col1_label:
            x_col, y_col = dataset_cols[0], dataset_cols[1]
        elif "(Y)" in col0_label and "(X)" in col1_label:
            x_col, y_col = dataset_cols[1], dataset_cols[0]
        else:
            x_col, y_col = dataset_cols[0], dataset_cols[1]
        x_idx = _find_column(x_col["column"], result.columns, "datasetColumns(X).column")
        y_idx = _find_column(y_col["column"], result.columns, "datasetColumns(Y).column")
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for row in result.rows:
            group_key = str(_to_json_safe(row[label_idx]))
            point = {"x": _to_json_safe(row[x_idx]), "y": _to_json_safe(row[y_idx])}
            groups.setdefault(group_key, []).append(point)
        return {"data": {"labels": [], "datasets": [
            {"label": gk, "data": gpts} for gk, gpts in groups.items()
        ]}}

    has_aggregation = any(
        ds.get("aggregation") and ds["aggregation"] != "none"
        for ds in dataset_cols
    )
    missing_data = opts.get("missingData")
    granularity = mapping.get("dateGranularity")
    has_granularity = bool(granularity and granularity != "none")
    breakdown_col = mapping.get("breakdownColumn")

    def _bucket(v: Any) -> Tuple[Any, Any]:
        """(sort_key, display) for a raw label value, honoring dateGranularity."""
        if has_granularity:
            return _bucket_label(_to_json_safe(v), granularity)
        sv = _to_json_safe(v)
        return sv, sv

    if breakdown_col:
        # ── Series breakdown: pivot the FIRST metric into one dataset per
        #    distinct breakdown value (Data-Studio "breakdown dimension").
        #    Multiple metrics + breakdown is out of scope; the first metric wins.
        breakdown_idx = _find_column(breakdown_col, result.columns, "breakdownColumn")
        measure = dataset_cols[0]
        m_idx = _find_column(measure["column"], result.columns, "datasetColumns[].column")
        agg = measure.get("aggregation") or "sum"
        if agg == "none":
            agg = "sum"

        label_keys: Dict[Any, Any] = {}
        labels: List[Any] = []
        series_seq: List[Any] = []
        series_seen = set()
        cells: Dict[Tuple[Any, Any], List[Any]] = {}
        for row in result.rows:
            sk, disp = _bucket(row[label_idx])
            if disp not in label_keys:
                label_keys[disp] = sk
                labels.append(disp)
            bv = _to_json_safe(row[breakdown_idx])
            if bv not in series_seen:
                series_seen.add(bv)
                series_seq.append(bv)
            cells.setdefault((disp, bv), []).append(_to_json_safe(row[m_idx]))

        if has_granularity:
            labels.sort(key=lambda d: label_keys[d])

        datasets: List[Dict[str, Any]] = []
        for bv in series_seq:
            data: List[Any] = []
            for d in labels:
                vals = cells.get((d, bv), [])
                data.append(_aggregate_values(vals, agg) if vals else None)
            if missing_data == "lineToZero":
                data = [0 if v is None else v for v in data]
            datasets.append({
                "label": str(bv) if bv is not None else "(null)",
                "data": data,
            })

    elif has_aggregation or has_granularity:
        # Group rows by (bucketed) labelColumn, aggregate each metric per group
        label_keys = {}
        label_order: List[Any] = []
        row_groups: Dict[Any, List[list]] = {}
        for row in result.rows:
            sk, lv = _bucket(row[label_idx])
            if lv not in row_groups:
                row_groups[lv] = []
                label_order.append(lv)
                label_keys[lv] = sk
            row_groups[lv].append(row)
        if has_granularity:
            label_order.sort(key=lambda d: label_keys[d])
        labels = label_order

        datasets = []
        for ds in dataset_cols:
            col = ds["column"]
            col_idx = _find_column(col, result.columns, "datasetColumns[].column")
            agg = ds.get("aggregation") or "sum"
            if agg == "none" and has_granularity:
                agg = "sum"
            data = []
            for lv in labels:
                vals = [_to_json_safe(r[col_idx]) for r in row_groups.get(lv, [])]
                data.append(
                    vals[0] if agg == "none" else _aggregate_values(vals, agg)
                )
            if missing_data == "lineToZero":
                data = [0 if v is None else v for v in data]
            dataset: Dict[str, Any] = {"label": ds.get("label") or col, "data": data}
            for key in _PASSTHROUGH_KEYS:
                if key in ds:
                    dataset[key] = ds[key]
            if ds.get("cumulative"):
                running = 0.0
                cum: List[Any] = []
                for v in dataset["data"]:
                    running += v if isinstance(v, (int, float)) else 0
                    cum.append(running)
                dataset["data"] = cum
            datasets.append(dataset)
    else:
        # 1:1 row mapping
        labels = [_to_json_safe(row[label_idx]) for row in result.rows]
        datasets = []
        for ds in dataset_cols:
            col = ds["column"]
            col_idx = _find_column(col, result.columns, "datasetColumns[].column")
            raw = [_to_json_safe(row[col_idx]) for row in result.rows]
            data = [0 if v is None else v for v in raw] if missing_data == "lineToZero" else raw
            dataset = {"label": ds.get("label") or col, "data": data}
            for key in _PASSTHROUGH_KEYS:
                if key in ds:
                    dataset[key] = ds[key]
            if ds.get("cumulative"):
                running = 0.0
                cum = []
                for v in dataset["data"]:
                    running += v if isinstance(v, (int, float)) else 0
                    cum.append(running)
                dataset["data"] = cum
            datasets.append(dataset)

    # Limit to last N points (after aggregation, before percentage normalization)
    number_of_points = opts.get("numberOfPoints")
    if number_of_points and number_of_points > 0 and datasets:
        labels = labels[-number_of_points:]
        datasets = [{**ds, "data": ds["data"][-number_of_points:]} for ds in datasets]

    # 100% stacked normalization
    if opts.get("stacked") == "percentage":
        for i in range(len(labels)):
            total = sum(
                ds["data"][i] for ds in datasets
                if i < len(ds["data"]) and isinstance(ds["data"][i], (int, float))
            )
            if total > 0:
                for ds in datasets:
                    if i < len(ds["data"]):
                        v = ds["data"][i]
                        ds["data"][i] = round((v / total) * 10000) / 100 if isinstance(v, (int, float)) else 0

    return {"data": {"labels": labels, "datasets": datasets}}


def transform_kpi(result: QueryResult, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Transform QueryResult into KPI widget config data.

    Mapping keys:
      - valueColumn: column for the main value
      - aggregation: how to aggregate multi-row results (sum, avg, count, min, max, first, last)
      - autoTrend: auto-calculate trend from multi-row results
      - periodLabel: trend calculation preference (e.g. "vs last month")
      - trendDateColumn: date column for period-based trend comparison
      - trendValueColumn: optional column for pre-computed trend numeric value

    Returns dict suitable for widget.config.
    """
    value_col = mapping.get("valueColumn")
    trend_col = mapping.get("trendValueColumn")

    # Incomplete mapping — return stub so editor dropdowns can still populate.
    if not value_col:
        return {"value": None}

    # Validate columns case-insensitively (precompute indices)
    value_idx = _find_column(value_col, result.columns, "valueColumn")
    trend_idx = _find_column(trend_col, result.columns, "trendValueColumn") if trend_col else None

    if not result.rows:
        logger.warning("KPI query returned 0 rows, returning null value")
        return {"value": None}

    # Aggregate value across all rows.
    aggregation = mapping.get("aggregation")
    if aggregation not in KPI_AGGREGATIONS:
        # Absent, stored null, or a method _aggregate_values doesn't know (its
        # trailing branch is "first"). A multi-row result almost never
        # means "show row 0" — that reading is what makes a 15k-row KPI render a
        # single cell. Single-row results are identical under either reading, so
        # they keep "first" and their meaning is unchanged. Deliberately narrower
        # than the blanket sum-default reverted in 5dbd4e7.
        aggregation = "sum" if len(result.rows) > 1 else "first"

    if getattr(result, "truncated", False) is True and aggregation != "first":
        # The engine capped the rows (settings.max_query_rows, enforced in every
        # connector and the DuckDB runner). Aggregating the prefix produces a
        # number that looks right and isn't — the failure mode this branch
        # exists to remove — so refuse, and say how to fix it. The serve path
        # turns this into a 400 with the widget's error banner + Fix button; the
        # bake path's SQL-fix round rewrites the query to aggregate in SQL.
        raise ValueError(
            f"KPI result was truncated at {result.row_count} rows, so a client-side "
            f"'{aggregation}' would be wrong. Aggregate in SQL "
            "(SELECT SUM(...) / COUNT(*) ...) or narrow the query."
        )

    # Delegate the ladder to _aggregate_values — the same helper the trend path
    # and transform_chart use. It is the only implementation that covers
    # countDistinct, which the editor and the agent params_doc both offer.
    # Non-null (not numeric-only) values mirror widgetTransform.ts, so the
    # editor's optimistic recompute and the server agree on text columns too.
    values = [
        v for v in (_to_json_safe(row[value_idx]) for row in result.rows)
        if v is not None
    ]
    value = _aggregate_values(values, aggregation)
    if value is None:
        # No non-null values, or none numeric for this aggregation — keep the
        # pre-existing "show row 0" behaviour for text-valued KPIs.
        value = _to_json_safe(result.rows[0][value_idx])

    config: Dict[str, Any] = {"value": value}

    # Auto-trend: derive trend from multi-row time-series results
    if mapping.get("autoTrend"):
        all_values = [
            v for v in (_to_json_safe(row[value_idx]) for row in result.rows)
            if isinstance(v, (int, float))
        ]
        if all_values:
            config["value"] = all_values[-1]

        period_label = mapping.get("periodLabel", "")
        date_col = mapping.get("trendDateColumn")

        # Period-based comparison using date column (case-insensitive)
        date_idx = None
        if date_col:
            for _i, _c in enumerate(result.columns):
                if _c.lower() == date_col.lower():
                    date_idx = _i
                    break
        if date_idx is not None and period_label in _DATE_BASED_PERIODS:
            today = date.today()
            cur_start, cur_end, prev_start, prev_end = _period_ranges(period_label, today)

            cur_values: List[float] = []
            prev_values: List[float] = []
            for row in result.rows:
                v = _to_json_safe(row[value_idx])
                if not isinstance(v, (int, float)):
                    continue
                d = _parse_date_value(row[date_idx])
                if d is None:
                    continue
                if cur_start <= d <= cur_end:
                    cur_values.append(float(v))
                elif prev_start <= d <= prev_end:
                    prev_values.append(float(v))

            cur_agg = _aggregate_values(cur_values, aggregation)
            prev_agg = _aggregate_values(prev_values, aggregation)

            if cur_agg is not None:
                config["value"] = cur_agg

            if cur_agg is not None and prev_agg is not None and prev_agg != 0:
                trend_pct = round(((cur_agg - prev_agg) / abs(prev_agg)) * 100, 2)
                direction = "up" if trend_pct > 0 else "down" if trend_pct < 0 else "neutral"
                config["trend"] = {"direction": direction, "value": trend_pct, "period": period_label}
            elif cur_agg is not None and prev_agg is not None:
                config["trend"] = {"direction": "neutral", "value": 0, "period": period_label}
            # If either period has no data, no trend emitted

        # Fallback: simple last-two-rows comparison
        elif len(all_values) >= 2:
            current = all_values[-1]
            previous = all_values[-2]
            if previous != 0:
                trend_pct = round(((current - previous) / abs(previous)) * 100, 2)
                direction = "up" if trend_pct > 0 else "down" if trend_pct < 0 else "neutral"
                config["trend"] = {"direction": direction, "value": trend_pct, "period": period_label}
            else:
                config["trend"] = {"direction": "neutral", "value": 0, "period": period_label}
        # autoTrend with < 2 rows and no date-based period: no trend emitted
    elif trend_idx is not None:
        trend_val = _to_json_safe(result.rows[0][trend_idx])
        if isinstance(trend_val, (int, float)) and trend_val > 0:
            direction = "up"
        elif isinstance(trend_val, (int, float)) and trend_val < 0:
            direction = "down"
        else:
            direction = "neutral"
        config["trend"] = {"direction": direction, "value": trend_val}

    return config


_TABLE_COLUMN_PASSTHROUGH_KEYS = (
    "sortable",
    "format",
    "filterable",
    "role",
    "displayType",
    "showBarValue",
    "compactNumbers",
    "aggregation",
    "comparisonCalc",
    "runningCalc",
)


def transform_table(result: QueryResult, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Transform QueryResult into table widget config data.

    Mapping keys:
      - columnConfig: list of {column, label, sortable?, format?, displayType?,
        aggregation?, comparisonCalc?, runningCalc?, ...} dicts — display
        fields in _TABLE_COLUMN_PASSTHROUGH_KEYS are copied onto the output
        column defs.

    Returns dict suitable for widget.config.
    """
    col_config = mapping.get("columnConfig", [])

    # Validate and precompute column indices (case-insensitive)
    col_indices = {}
    for cc in col_config:
        col = cc.get("column")
        col_indices[col] = _find_column(col, result.columns, "columnConfig[].column")

    columns = []
    for cc in col_config:
        col_def: Dict[str, Any] = {
            "key": cc["column"],
            "label": cc.get("label", cc["column"]),
        }
        for key in _TABLE_COLUMN_PASSTHROUGH_KEYS:
            if key in cc:
                col_def[key] = cc[key]
        columns.append(col_def)

    rows = []
    for row in result.rows:
        row_dict: Dict[str, Any] = {}
        for cc in col_config:
            col = cc["column"]
            row_dict[col] = _to_json_safe(row[col_indices[col]])
        rows.append(row_dict)

    return {"columns": columns, "rows": rows}


def transform_pivot_table(result: QueryResult, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Transform QueryResult into pivot-table widget config data.

    Passthrough (same shape as transform_table): returns the granular
    {columns, rows} for the referenced columns. The actual pivot — grouping
    row/column dimensions and aggregating metrics, with subtotals/grand totals
    and expand-collapse — is computed client-side in DashboardWidgetPivotTable.vue.

    Mapping keys:
      - columnConfig: list of {column, label?} — union of row dims, column dims,
        and value columns the pivot references.
    """
    return transform_table(result, mapping)


def transform_widget_data(result: QueryResult, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch to the correct transform function based on mapping.type.

    Args:
        result: QueryResult from connector.execute_query()
        mapping: Mapping config dict with a 'type' key (chart | kpi | table | pivot_table)

    Returns:
        Widget config dict ready to merge into widget.widget.config

    Raises:
        ValueError: If mapping.type is unsupported or column names mismatch.
    """
    mapping_type = mapping.get("type")
    if mapping_type == "chart":
        return transform_chart(result, mapping)
    elif mapping_type == "kpi":
        return transform_kpi(result, mapping)
    elif mapping_type == "table":
        return transform_table(result, mapping)
    elif mapping_type == "pivot_table":
        return transform_pivot_table(result, mapping)
    else:
        raise ValueError(
            f"Unsupported mapping type: '{mapping_type}'. Must be one of: chart, kpi, table, pivot_table"
        )
