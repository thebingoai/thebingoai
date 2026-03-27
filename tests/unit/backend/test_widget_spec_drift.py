"""
Drift test: ensures JSON widget schemas stay in sync with TypeScript types.

Parses TypeScript interfaces from dashboard.ts and chart.ts, then verifies
every field appears in the corresponding JSON schema. Fails if a developer
adds a field in TypeScript but forgets to update the JSON schema.
"""

import re
from pathlib import Path

import pytest

from backend.agents.dashboard_agent.widget_specs import load_schema

# Paths relative to the bingo submodule root
_BINGO_ROOT = Path(__file__).resolve().parents[3]
_DASHBOARD_TS = _BINGO_ROOT / "frontend" / "types" / "dashboard.ts"
_CHART_TS = _BINGO_ROOT / "frontend" / "types" / "chart.ts"


def _parse_ts_interface_fields(file_path: Path, interface_name: str) -> set[str]:
    """
    Extract top-level field names from a TypeScript interface.

    Handles:
      - field: type
      - field?: type
      - field?: { nested }  (extracts outer field only)
    """
    content = file_path.read_text()

    # Find the interface block
    pattern = rf"export\s+interface\s+{interface_name}\s*\{{(.*?)\}}"
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return set()

    body = match.group(1)
    fields = set()

    # Match field names (handles optional ? and various type annotations)
    for field_match in re.finditer(r"^\s+(\w+)\??:\s", body, re.MULTILINE):
        field_name = field_match.group(1)
        # Skip 'type' field — it's the discriminator, not a user-configured field
        if field_name != "type":
            fields.add(field_name)

    return fields


def _get_all_schema_fields(schema: dict, section: str) -> set[str]:
    """Extract all field names from a schema section, including nested fields."""
    section_data = schema.get(section, {})
    fields = set()
    for name, value in section_data.items():
        fields.add(name)
        # Also check nested 'fields' and 'items'
        if isinstance(value, dict):
            for sub_key in ("fields", "items"):
                sub = value.get(sub_key, {})
                if isinstance(sub, dict):
                    fields.update(
                        k for k, v in sub.items() if isinstance(v, dict)
                    )
    return fields


class TestKpiSchemaSync:
    """KPI schema must cover all fields from KpiWidgetConfig and KpiDataSourceMapping."""

    def test_config_fields(self):
        ts_fields = _parse_ts_interface_fields(_DASHBOARD_TS, "KpiWidgetConfig")
        schema_fields = _get_all_schema_fields(load_schema("kpi"), "config")

        # Runtime-populated by the backend (not agent-configured)
        runtime_fields = {"value", "trend", "sparkline", "sparklineLabels"}
        # Nested inside the 'trend' sub-object (not top-level config fields)
        nested_fields = {"direction", "period"}
        ts_fields -= runtime_fields | nested_fields

        missing = ts_fields - schema_fields
        assert not missing, (
            f"KPI config schema missing fields from KpiWidgetConfig: {missing}"
        )

    def test_mapping_fields(self):
        ts_fields = _parse_ts_interface_fields(_DASHBOARD_TS, "KpiDataSourceMapping")
        schema_fields = _get_all_schema_fields(load_schema("kpi"), "mapping")

        missing = ts_fields - schema_fields
        assert not missing, (
            f"KPI mapping schema missing fields from KpiDataSourceMapping: {missing}"
        )


class TestChartSchemaSync:
    """Chart schema must cover ChartConfig and ChartDataSourceMapping fields."""

    def test_config_fields(self):
        ts_fields = _parse_ts_interface_fields(_CHART_TS, "ChartConfig")
        schema_fields = _get_all_schema_fields(load_schema("chart"), "config")

        # Runtime-populated by the backend (not agent-configured)
        runtime_fields = {"data"}
        # Nested inside the 'data' sub-object
        nested_fields = {"labels", "datasets"}
        ts_fields -= runtime_fields | nested_fields

        missing = ts_fields - schema_fields
        assert not missing, (
            f"Chart config schema missing fields from ChartConfig: {missing}"
        )

    def test_options_fields(self):
        ts_fields = _parse_ts_interface_fields(_CHART_TS, "ChartOptions")
        schema = load_schema("chart")
        # Options are nested under config.options.fields
        options_fields = set()
        options_def = schema.get("config", {}).get("options", {})
        if isinstance(options_def, dict):
            for k, v in options_def.get("fields", {}).items():
                options_fields.add(k)

        # Internal Chart.js defaults — not agent-configured
        internal_fields = {"responsive", "maintainAspectRatio", "aspectRatio"}
        ts_fields -= internal_fields

        missing = ts_fields - options_fields
        assert not missing, (
            f"Chart options schema missing fields from ChartOptions: {missing}"
        )

    def test_mapping_fields(self):
        ts_fields = _parse_ts_interface_fields(_DASHBOARD_TS, "ChartDataSourceMapping")
        schema_fields = _get_all_schema_fields(load_schema("chart"), "mapping")

        missing = ts_fields - schema_fields
        assert not missing, (
            f"Chart mapping schema missing fields from ChartDataSourceMapping: {missing}"
        )


class TestTableSchemaSync:
    """Table schema must cover TableWidgetConfig and TableDataSourceMapping."""

    def test_config_fields(self):
        ts_fields = _parse_ts_interface_fields(_DASHBOARD_TS, "TableWidgetConfig")
        schema_fields = _get_all_schema_fields(load_schema("table"), "config")

        # 'rows' is runtime-populated
        runtime_fields = {"rows"}
        ts_fields -= runtime_fields

        missing = ts_fields - schema_fields
        assert not missing, (
            f"Table config schema missing fields from TableWidgetConfig: {missing}"
        )

    def test_mapping_fields(self):
        ts_fields = _parse_ts_interface_fields(_DASHBOARD_TS, "TableDataSourceMapping")
        schema_fields = _get_all_schema_fields(load_schema("table"), "mapping")

        missing = ts_fields - schema_fields
        assert not missing, (
            f"Table mapping schema missing fields from TableDataSourceMapping: {missing}"
        )


class TestFilterSchemaSync:
    """Filter schema must cover FilterWidgetConfig and FilterControl."""

    def test_config_fields(self):
        ts_fields = _parse_ts_interface_fields(_DASHBOARD_TS, "FilterWidgetConfig")
        schema_fields = _get_all_schema_fields(load_schema("filter"), "config")

        missing = ts_fields - schema_fields
        assert not missing, (
            f"Filter config schema missing fields from FilterWidgetConfig: {missing}"
        )

    def test_control_fields(self):
        ts_fields = _parse_ts_interface_fields(_DASHBOARD_TS, "FilterControl")
        schema = load_schema("filter")
        # Control fields are nested under config.controls.items
        control_items = schema.get("config", {}).get("controls", {}).get("items", {})
        schema_fields = set()
        for k, v in control_items.items():
            if isinstance(v, dict):
                schema_fields.add(k)
                # Also check nested fields (e.g., optionsSource.fields)
                for sub_key in ("fields",):
                    sub = v.get(sub_key, {})
                    if isinstance(sub, dict):
                        schema_fields.update(sub.keys())

        # 'type' is a valid control field (not the discriminator here)
        ts_fields_with_type = ts_fields | {"type"}

        missing = ts_fields_with_type - schema_fields
        assert not missing, (
            f"Filter control schema missing fields from FilterControl: {missing}"
        )


class TestTextSchemaSync:
    """Text schema must cover TextWidgetConfig."""

    def test_config_fields(self):
        ts_fields = _parse_ts_interface_fields(_DASHBOARD_TS, "TextWidgetConfig")
        schema_fields = _get_all_schema_fields(load_schema("text"), "config")

        missing = ts_fields - schema_fields
        assert not missing, (
            f"Text config schema missing fields from TextWidgetConfig: {missing}"
        )
