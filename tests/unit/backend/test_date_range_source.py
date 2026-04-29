"""Tests for dateRangeSource additions to filter schema and guidance."""

import json
import pathlib
import re

import pytest

SCHEMA_PATH = (
    pathlib.Path(__file__).resolve().parents[3]
    / "backend"
    / "agents"
    / "dashboard_agent"
    / "widget_specs"
    / "schemas"
    / "filter.json"
)


class TestFilterSchema:
    def test_dateRangeSource_in_schema(self):
        """filter.json has dateRangeSource with connectionId + sql fields."""
        schema = json.loads(SCHEMA_PATH.read_text())
        items = schema["config"]["controls"]["items"]
        assert "dateRangeSource" in items
        drs = items["dateRangeSource"]
        assert drs["type"] == "object"
        assert "connectionId" in drs["fields"]
        assert "sql" in drs["fields"]


class TestFilterGuidance:
    def test_guidance_mentions_dateRangeSource(self):
        """FILTER_GUIDANCE contains dateRangeSource, min_date, max_date."""
        from backend.agents.dashboard_agent.widget_specs.guidance.filter import (
            FILTER_GUIDANCE,
        )

        assert "dateRangeSource" in FILTER_GUIDANCE
        assert "min_date" in FILTER_GUIDANCE
        assert "max_date" in FILTER_GUIDANCE

    def test_example_has_dateRangeSource(self):
        """Example JSON in guidance has dateRangeSource on date_range control."""
        from backend.agents.dashboard_agent.widget_specs.guidance.filter import (
            FILTER_GUIDANCE,
        )

        match = re.search(r"```json\s*(\{.*?\})\s*```", FILTER_GUIDANCE, re.DOTALL)
        assert match, "No JSON example found in guidance"
        example = json.loads(match.group(1))
        controls = example["widget"]["config"]["controls"]
        date_controls = [c for c in controls if c["type"] == "date_range"]
        assert len(date_controls) >= 1, "No date_range control in example"
        assert "dateRangeSource" in date_controls[0], "date_range control missing dateRangeSource"
        drs = date_controls[0]["dateRangeSource"]
        assert "connectionId" in drs
        assert "sql" in drs
        assert "min_date" in drs["sql"].lower()
        assert "max_date" in drs["sql"].lower()


class TestDateRangeDefault:
    def test_dateRangeDefault_in_schema(self):
        """filter.json has dateRangeDefault with allowed enum values."""
        schema = json.loads(SCHEMA_PATH.read_text())
        items = schema["config"]["controls"]["items"]
        assert "dateRangeDefault" in items
        drd = items["dateRangeDefault"]
        assert drd["type"] == "enum"
        assert set(drd["values"]) == {"full", "7d", "30d", "90d", "ytd"}
        assert drd["required"] is False

    def test_guidance_mentions_dateRangeDefault(self):
        """FILTER_GUIDANCE documents dateRangeDefault and all its values."""
        from backend.agents.dashboard_agent.widget_specs.guidance.filter import (
            FILTER_GUIDANCE,
        )
        assert "dateRangeDefault" in FILTER_GUIDANCE
        for value in ("full", "7d", "30d", "90d", "ytd"):
            assert value in FILTER_GUIDANCE

    def test_guidance_example_has_dateRangeDefault(self):
        """Example JSON in guidance sets dateRangeDefault on the date_range control."""
        from backend.agents.dashboard_agent.widget_specs.guidance.filter import (
            FILTER_GUIDANCE,
        )
        schema = json.loads(SCHEMA_PATH.read_text())
        allowed_values = set(schema["config"]["controls"]["items"]["dateRangeDefault"]["values"])

        match = re.search(r"```json\s*(\{.*?\})\s*```", FILTER_GUIDANCE, re.DOTALL)
        assert match, "No JSON example found in guidance"
        example = json.loads(match.group(1))
        controls = example["widget"]["config"]["controls"]
        date_controls = [c for c in controls if c["type"] == "date_range"]
        assert len(date_controls) >= 1
        assert "dateRangeDefault" in date_controls[0]
        assert date_controls[0]["dateRangeDefault"] in allowed_values
