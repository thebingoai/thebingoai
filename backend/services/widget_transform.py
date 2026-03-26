"""Widget Transform — Pure functions to convert QueryResult into widget config dicts."""
from decimal import Decimal
from datetime import date, datetime
from typing import Any, Dict

from backend.connectors.base import QueryResult


def _to_json_safe(value: Any) -> Any:
    """Convert database-native types to JSON-serializable equivalents."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def transform_chart(result: QueryResult, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Transform QueryResult into chart widget config data.

    Mapping keys:
      - labelColumn: column name to use for chart labels (x-axis / slices)
      - datasetColumns: list of {column, label} dicts for datasets

    Returns dict suitable for widget.config (merged with existing chart-level fields).
    """
    label_col = mapping.get("labelColumn")
    dataset_cols = mapping.get("datasetColumns", [])

    if label_col not in result.columns:
        raise ValueError(
            f"Column '{label_col}' not found in query results. "
            f"Available columns: {result.columns}"
        )
    for ds in dataset_cols:
        col = ds.get("column")
        if col not in result.columns:
            raise ValueError(
                f"Column '{col}' not found in query results. "
                f"Available columns: {result.columns}"
            )

    label_idx = result.columns.index(label_col)
    labels = [_to_json_safe(row[label_idx]) for row in result.rows]

    _PASSTHROUGH_KEYS = {
        "backgroundColor", "borderColor", "borderWidth", "fill",
        "tension", "pointRadius",
    }

    datasets = []
    for ds in dataset_cols:
        col = ds["column"]
        col_idx = result.columns.index(col)
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
      - valueColumn: column for the main value (first row)
      - trendValueColumn: optional column for trend numeric value (first row)
      - sparklineColumn: optional column for sparkline series (all rows)

    Returns dict suitable for widget.config.
    """
    value_col = mapping.get("valueColumn")
    trend_col = mapping.get("trendValueColumn")
    sparkline_col = mapping.get("sparklineColumn")

    if value_col not in result.columns:
        raise ValueError(
            f"Column '{value_col}' not found in query results. "
            f"Available columns: {result.columns}"
        )
    if trend_col and trend_col not in result.columns:
        raise ValueError(
            f"Column '{trend_col}' not found in query results. "
            f"Available columns: {result.columns}"
        )
    if sparkline_col and sparkline_col not in result.columns:
        raise ValueError(
            f"Column '{sparkline_col}' not found in query results. "
            f"Available columns: {result.columns}"
        )
    if not result.rows:
        raise ValueError("Query returned no rows — cannot build KPI widget")

    value_idx = result.columns.index(value_col)
    first_row = result.rows[0]
    value = _to_json_safe(first_row[value_idx])

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

        if len(all_values) >= 2:
            current = all_values[-1]
            previous = all_values[-2]
            if previous != 0:
                trend_pct = round(((current - previous) / abs(previous)) * 100, 2)
                direction = "up" if trend_pct > 0 else "down" if trend_pct < 0 else "neutral"
                config["trend"] = {
                    "direction": direction,
                    "value": trend_pct,
                    "period": mapping.get("periodLabel", ""),
                }
            else:
                config["trend"] = {"direction": "neutral", "value": 0, "period": mapping.get("periodLabel", "")}
        # autoTrend with < 2 rows: no trend emitted
    elif trend_col:
        trend_idx = result.columns.index(trend_col)
        trend_val = _to_json_safe(first_row[trend_idx])
        if isinstance(trend_val, (int, float)) and trend_val > 0:
            direction = "up"
        elif isinstance(trend_val, (int, float)) and trend_val < 0:
            direction = "down"
        else:
            direction = "neutral"
        config["trend"] = {"direction": direction, "value": trend_val}

    if not mapping.get("autoTrend") and sparkline_col:
        spark_idx = result.columns.index(sparkline_col)
        config["sparkline"] = [_to_json_safe(row[spark_idx]) for row in result.rows]

    return config


def transform_table(result: QueryResult, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Transform QueryResult into table widget config data.

    Mapping keys:
      - columnConfig: list of {column, label, sortable?, format?} dicts

    Returns dict suitable for widget.config.
    """
    col_config = mapping.get("columnConfig", [])

    for cc in col_config:
        col = cc.get("column")
        if col not in result.columns:
            raise ValueError(
                f"Column '{col}' not found in query results. "
                f"Available columns: {result.columns}"
            )

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
            col_idx = result.columns.index(col)
            row_dict[col] = _to_json_safe(row[col_idx])
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
