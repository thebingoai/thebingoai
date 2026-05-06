"""Tests for dbt project synthesizer."""
import os
import tempfile
import yaml

import pytest


def test_write_sources_yml_empty():
    """Empty source list produces valid sources.yml with no sources."""
    from backend.transforms.project_synth import _write_sources_yml

    with tempfile.TemporaryDirectory() as tmpdir:
        _write_sources_yml(tmpdir, [])
        with open(os.path.join(tmpdir, "sources.yml")) as f:
            content = yaml.safe_load(f)
        assert content["version"] == 2
        assert content["sources"] == []


def test_write_sources_yml_with_tables():
    """Source tables appear in sources.yml under the 'pipelines' source."""
    from backend.transforms.project_synth import _write_sources_yml

    with tempfile.TemporaryDirectory() as tmpdir:
        _write_sources_yml(tmpdir, ["fb_ads_act_123", "notion_workspace_42"])
        with open(os.path.join(tmpdir, "sources.yml")) as f:
            content = yaml.safe_load(f)
        assert content["sources"][0]["name"] == "pipelines"
        table_names = [t["name"] for t in content["sources"][0]["tables"]]
        assert "fb_ads_act_123" in table_names
        assert "notion_workspace_42" in table_names


def test_write_sources_yml_deduplicates():
    """Duplicate table names are written only once."""
    from backend.transforms.project_synth import _write_sources_yml

    with tempfile.TemporaryDirectory() as tmpdir:
        _write_sources_yml(tmpdir, ["tbl", "tbl", "tbl"])
        with open(os.path.join(tmpdir, "sources.yml")) as f:
            content = yaml.safe_load(f)
        tables = content["sources"][0]["tables"]
        names = [t["name"] for t in tables]
        assert names.count("tbl") == 1


def test_write_model_sql_table():
    """Table model gets config(materialized='table') block prepended."""
    from backend.transforms.project_synth import _write_model_sql

    class FakeModel:
        name = "my_table"
        sql = "SELECT id, name FROM source_tbl"
        materialization = "table"
        unique_key = None

    with tempfile.TemporaryDirectory() as tmpdir:
        _write_model_sql(tmpdir, FakeModel())
        with open(os.path.join(tmpdir, "my_table.sql")) as f:
            sql = f.read()
        assert 'config(materialized="table")' in sql
        assert "SELECT id, name FROM source_tbl" in sql


def test_write_model_sql_incremental():
    """Incremental model includes unique_key in config block."""
    from backend.transforms.project_synth import _write_model_sql

    class FakeModel:
        name = "my_incremental"
        sql = "SELECT id, amount FROM orders"
        materialization = "incremental"
        unique_key = "id"

    with tempfile.TemporaryDirectory() as tmpdir:
        _write_model_sql(tmpdir, FakeModel())
        with open(os.path.join(tmpdir, "my_incremental.sql")) as f:
            sql = f.read()
        assert 'materialized="incremental"' in sql
        assert 'unique_key="id"' in sql


def test_safe_write_atomic(tmp_path):
    """_safe_write writes correct content and cleans up .tmp on success."""
    from backend.transforms.project_synth import _safe_write

    target = str(tmp_path / "out.txt")
    _safe_write(target, "hello world")
    assert open(target).read() == "hello world"
    assert not os.path.exists(target + ".tmp")
