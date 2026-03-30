"""Widget Transform — Pure functions to convert QueryResult into widget config dicts."""
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


def _aggregate_values(values: List[float], aggregation: str) -> Optional[float]:
    """Aggregate a list of values using the given method."""
    if not values:
        return None
    if aggregation == "sum":
        return sum(values)
    elif aggregation == "avg":
        return round(sum(values) / len(values), 2)
    elif aggregation == "count":
        return float(len(values))
    elif aggregation == "min":
        return min(values)
    elif aggregation == "max":
        return max(values)
    elif aggregation == "last":
        return values[-1]
    else:  # "first" or unrecognized
        return values[0]


def transform_chart(result: QueryResult, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Transform QueryResult into chart widget config data.

    Mapping keys:
      - labelColumn: column name to use for chart labels (x-axis / slices)
      - datasetColumns: list of {column, label} dicts for datasets

    Returns dict suitable for widget.config (merged with existing chart-level fields).
    """
    label_col = mapping.get("labelColumn")
    dataset_cols = mapping.get("datasetColumns", [])

    label_idx = _find_column(label_col, result.columns, "labelColumn")
    labels = [_to_json_safe(row[label_idx]) for row in result.rows]

    _PASSTHROUGH_KEYS = {
        "backgroundColor", "borderColor", "borderWidth", "fill",
        "tension", "pointRadius",
    }

    datasets = []
    for ds in dataset_cols:
        col = ds["column"]
        col_idx = _find_column(col, result.columns, "datasetColumns[].column")
        dataset: Dict[str, Any] = {
            "label": ds.get("label", col),
            "data": [_to_json_safe(row[col_idx]) for row in result.rows],
        }
        for key in _PASSTHROUGH_KEYS:
            if key in ds:
                dataset[key] = ds[key]
        datasets.append(dataset)

    return {"data": {"labels": labels, "datasets": datasets}}


def transform_kpi(result: QueryResult, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Transform QueryResult into KPI widget config data.

    Mapping keys:
      - valueColumn: column for the main value
      - aggregation: how to aggregate multi-row results (sum, avg, count, min, max, first, last)
      - autoTrend: auto-calculate trend and sparkline from multi-row results
      - periodLabel: trend calculation preference (e.g. "vs last month")
      - trendDateColumn: date column for period-based trend comparison
      - trendValueColumn: optional column for pre-computed trend numeric value
      - sparklineXColumn: optional column for sparkline x-axis labels
      - sparklineYColumn: optional column for sparkline y-axis values

    Returns dict suitable for widget.config.
    """
    value_col = mapping.get("valueColumn")
    trend_col = mapping.get("trendValueColumn")
    sparkline_x_col = mapping.get("sparklineXColumn")
    sparkline_y_col = mapping.get("sparklineYColumn")

    # Validate columns case-insensitively (precompute indices)
    value_idx = _find_column(value_col, result.columns, "valueColumn")
    trend_idx = _find_column(trend_col, result.columns, "trendValueColumn") if trend_col else None
    sparkline_x_idx = _find_column(sparkline_x_col, result.columns, "sparklineXColumn") if sparkline_x_col else None
    sparkline_y_idx = _find_column(sparkline_y_col, result.columns, "sparklineYColumn") if sparkline_y_col else None

    if not result.rows:
        logger.warning("KPI query returned 0 rows, returning null value")
        return {"value": None}

    # Aggregate value across all rows
    aggregation = mapping.get("aggregation", "first")
    all_numeric = [
        v for v in (_to_json_safe(row[value_idx]) for row in result.rows)
        if isinstance(v, (int, float))
    ]

    if not all_numeric:
        value = _to_json_safe(result.rows[0][value_idx])
    elif aggregation == "sum":
        value = sum(all_numeric)
    elif aggregation == "avg":
        value = round(sum(all_numeric) / len(all_numeric), 2)
    elif aggregation == "count":
        value = len(all_numeric)
    elif aggregation == "min":
        value = min(all_numeric)
    elif aggregation == "max":
        value = max(all_numeric)
    elif aggregation == "last":
        value = all_numeric[-1]
    else:  # "first" or unrecognized
        value = all_numeric[0]

    config: Dict[str, Any] = {"value": value}

    # Auto-trend: derive trend + sparkline from multi-row time-series results
    if mapping.get("autoTrend"):
        all_values = [
            v for v in (_to_json_safe(row[value_idx]) for row in result.rows)
            if isinstance(v, (int, float))
        ]
        if all_values:
            config["sparkline"] = all_values
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

    if sparkline_y_idx is not None:
        sort_col = mapping.get("sparklineSortColumn")
        sort_dir = mapping.get("sparklineSortDirection", "asc")
        rows = result.rows
        if sort_col:
            sort_idx_val = None
            for _i, _c in enumerate(result.columns):
                if _c.lower() == sort_col.lower():
                    sort_idx_val = _i
                    break
            if sort_idx_val is not None:
                rows = sorted(rows, key=lambda r: (r[sort_idx_val] is None, r[sort_idx_val]), reverse=(sort_dir == "desc"))
        config["sparkline"] = [_to_json_safe(row[sparkline_y_idx]) for row in rows]
        if sparkline_x_idx is not None:
            config["sparklineLabels"] = [str(_to_json_safe(row[sparkline_x_idx])) for row in rows]

    return config


def transform_table(result: QueryResult, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Transform QueryResult into table widget config data.

    Mapping keys:
      - columnConfig: list of {column, label, sortable?, format?} dicts

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
        if "sortable" in cc:
            col_def["sortable"] = cc["sortable"]
        if "format" in cc:
            col_def["format"] = cc["format"]
        columns.append(col_def)

    rows = []
    for row in result.rows:
        row_dict: Dict[str, Any] = {}
        for cc in col_config:
            col = cc["column"]
            row_dict[col] = _to_json_safe(row[col_indices[col]])
        rows.append(row_dict)

    return {"columns": columns, "rows": rows}


def transform_widget_data(result: QueryResult, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch to the correct transform function based on mapping.type.

    Args:
        result: QueryResult from connector.execute_query()
        mapping: Mapping config dict with a 'type' key (chart | kpi | table)

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
    else:
        raise ValueError(
            f"Unsupported mapping type: '{mapping_type}'. Must be one of: chart, kpi, table"
        )
