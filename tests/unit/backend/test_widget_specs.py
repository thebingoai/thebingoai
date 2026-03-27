"""Tests for the widget spec registry and renderer."""

import json
from pathlib import Path

import pytest

from backend.agents.dashboard_agent.widget_specs import (
    get_widget_spec,
    get_available_types,
    load_schema,
    render_fields,
)

WIDGET_TYPES = ["kpi", "chart", "table", "filter", "text"]
SCHEMAS_DIR = (
    Path(__file__).resolve().parents[3]
    / "backend"
    / "agents"
    / "dashboard_agent"
    / "widget_specs"
    / "schemas"
)


class TestGetWidgetSpec:
    """Test the main get_widget_spec() function."""

    @pytest.mark.parametrize("widget_type", WIDGET_TYPES)
    def test_returns_non_empty_string(self, widget_type: str):
        spec = get_widget_spec(widget_type)
        assert spec is not None
        assert isinstance(spec, str)
        assert len(spec) > 100  # Should be substantial

    def test_unknown_type_returns_none(self):
        assert get_widget_spec("unknown_widget") is None

    def test_available_types(self):
        types = get_available_types()
        assert set(types) == set(WIDGET_TYPES)


class TestSchemaLoading:
    """Test that all JSON schemas are valid and loadable."""

    @pytest.mark.parametrize("widget_type", WIDGET_TYPES)
    def test_schema_file_exists(self, widget_type: str):
        schema_path = SCHEMAS_DIR / f"{widget_type}.json"
        assert schema_path.exists(), f"Missing schema: {schema_path}"

    @pytest.mark.parametrize("widget_type", WIDGET_TYPES)
    def test_schema_is_valid_json(self, widget_type: str):
        schema = load_schema(widget_type)
        assert isinstance(schema, dict)
        assert schema.get("widget_type") == widget_type

    @pytest.mark.parametrize("widget_type", WIDGET_TYPES)
    def test_schema_has_config(self, widget_type: str):
        schema = load_schema(widget_type)
        assert "config" in schema, f"{widget_type} schema missing 'config'"

    @pytest.mark.parametrize("widget_type", WIDGET_TYPES)
    def test_schema_has_position_defaults(self, widget_type: str):
        schema = load_schema(widget_type)
        assert "position_defaults" in schema


class TestRenderFields:
    """Test the auto-generated field documentation."""

    @pytest.mark.parametrize("widget_type", WIDGET_TYPES)
    def test_rendered_fields_contain_all_config_fields(self, widget_type: str):
        schema = load_schema(widget_type)
        rendered = render_fields(schema)
        for field_name in schema.get("config", {}):
            assert field_name in rendered, (
                f"Rendered spec for '{widget_type}' missing config field: {field_name}"
            )

    @pytest.mark.parametrize("widget_type", ["kpi", "chart", "table"])
    def test_rendered_fields_contain_all_mapping_fields(self, widget_type: str):
        schema = load_schema(widget_type)
        rendered = render_fields(schema)
        for field_name in schema.get("mapping", {}):
            assert field_name in rendered, (
                f"Rendered spec for '{widget_type}' missing mapping field: {field_name}"
            )

    def test_filter_has_no_mapping(self):
        schema = load_schema("filter")
        assert "mapping" not in schema

    def test_text_has_no_mapping(self):
        schema = load_schema("text")
        assert "mapping" not in schema


class TestSpecCompleteness:
    """Test that rendered specs include guidance sections."""

    @pytest.mark.parametrize("widget_type", WIDGET_TYPES)
    def test_spec_includes_guidance(self, widget_type: str):
        spec = get_widget_spec(widget_type)
        # Every spec should have both auto-generated fields and hand-written guidance
        assert "Config Fields" in spec or "config" in spec.lower()
        assert "Best Practices" in spec or "Example" in spec or "Usage" in spec
