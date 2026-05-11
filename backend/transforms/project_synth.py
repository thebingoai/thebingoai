"""dbt project synthesizer — writes a per-Org dbt project to a persistent volume.

Per-Org project root: DBT_PROJECTS_ROOT/org_{scope_id}/
  dbt_project.yml
  profiles.yml
  models/
    sources.yml  — Pipeline outputs for this scope only
    <model_name>.sql  — one file per DbtModel

Lazy synth-on-write: called after any DbtModel create/update for the scope.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import yaml

logger = logging.getLogger(__name__)

DBT_PROJECTS_ROOT = os.environ.get("DBT_PROJECTS_ROOT", "/app/data/dbt_projects")


def _project_dir(scope_id: str) -> str:
    return os.path.join(DBT_PROJECTS_ROOT, f"org_{scope_id}")


def synthesize_project(scope, db) -> str:
    """Write/update the dbt project for *scope* and return the project directory path.

    Reads all DbtModels for the scope from the database.
    Reads all Pipeline target_tables for the scope from the database.
    Determines the DataPlane type to pick the right dbt adapter.

    Returns the project directory path.
    """
    from backend.models.transforms import DbtModel
    from backend.models.pipeline import Pipeline
    from backend.services.data_plane_service import get_default_plane
    from backend.data_plane.local_filesystem import LocalFilesystemDataPlane

    project_dir = _project_dir(scope.id)
    models_dir = os.path.join(project_dir, "models")
    os.makedirs(models_dir, exist_ok=True)

    # Load the DataPlane for this scope
    plane = get_default_plane(scope, db)
    profile_config = plane.to_dbt_profile()

    # For LocalFilesystemDataPlane: substitute the actual DuckDB path
    if isinstance(plane, LocalFilesystemDataPlane):
        # Point DuckDB at a persistent file in the org's data_plane dir
        duckdb_path = os.path.join(plane._root, scope.as_path(), "dbt.duckdb")
        profile_config = {**profile_config, "path": duckdb_path}

    # Write dbt_project.yml
    project_name = f"bingo_org_{scope.id.replace('-', '_')}"
    _write_dbt_project_yml(project_dir, project_name)

    # Write profiles.yml
    _write_profiles_yml(project_dir, project_name, profile_config)

    # Load same-scope Pipeline target tables for sources.yml
    pipelines = (
        db.query(Pipeline)
        .filter(
            Pipeline.owner_scope_kind == scope.kind,
            Pipeline.owner_scope_id == scope.id,
            Pipeline.enabled == True,   # noqa: E712
        )
        .all()
    )
    source_tables = [p.target_table for p in pipelines]

    # For LocalFilesystemDataPlane: build external_location glob so dbt-duckdb
    # can read pipeline Parquet outputs as external tables.
    sources_external_location = None
    if isinstance(plane, LocalFilesystemDataPlane):
        scope_root = os.path.join(plane._root, scope.as_path())
        sources_external_location = (
            f"read_parquet('{scope_root}/" + "{name}/dt=*/*.parquet', hive_partitioning=true)"
        )

    # Write models/sources.yml
    _write_sources_yml(models_dir, source_tables, sources_external_location)

    # Write one .sql file per DbtModel
    models = (
        db.query(DbtModel)
        .filter(
            DbtModel.owner_scope_kind == scope.kind,
            DbtModel.owner_scope_id == scope.id,
        )
        .all()
    )
    for model in models:
        _write_model_sql(models_dir, model)

    logger.info(
        "synthesize_project: wrote dbt project for scope %s (%d models, %d sources)",
        scope.as_path(), len(models), len(source_tables),
    )
    return project_dir


def _write_dbt_project_yml(project_dir: str, project_name: str) -> None:
    content = {
        "name": project_name,
        "version": "1.0.0",
        "config-version": 2,
        "profile": project_name,
        "model-paths": ["models"],
        "models": {
            project_name: {
                "+materialized": "table",
                # Disable Jinja macros beyond the allow-list (P4.2)
                # dbt-core 1.7+ honours restrict-access for macros; custom macros dir is absent.
            },
        },
    }
    _safe_write(os.path.join(project_dir, "dbt_project.yml"), yaml.dump(content, default_flow_style=False))


def _write_profiles_yml(project_dir: str, project_name: str, target_config: dict) -> None:
    content = {
        project_name: {
            "target": "default",
            "outputs": {
                "default": target_config,
            },
        },
    }
    _safe_write(os.path.join(project_dir, "profiles.yml"), yaml.dump(content, default_flow_style=False))


def _write_sources_yml(
    models_dir: str,
    table_names: list[str],
    external_location: str | None = None,
) -> None:
    """Write sources.yml declaring each Pipeline output as a dbt source.

    When *external_location* is provided (LocalFilesystemDataPlane), each source
    table gets an external_location meta so dbt-duckdb reads the Parquet directly.
    """
    if not table_names:
        sources_content = {"version": 2, "sources": []}
    else:
        source = {
            "name": "pipelines",
            "tables": [{"name": t} for t in sorted(set(table_names))],
        }
        if external_location:
            source["meta"] = {"external_location": external_location}
        sources_content = {"version": 2, "sources": [source]}
    _safe_write(os.path.join(models_dir, "sources.yml"), yaml.dump(sources_content, default_flow_style=False))


def _write_model_sql(models_dir: str, model) -> None:
    """Write a single model's .sql file with a Jinja config block prepended."""
    config_args = f'materialized="{model.materialization}"'
    if model.materialization == "incremental" and model.unique_key:
        config_args += f', unique_key="{model.unique_key}"'

    sql = f"{{{{ config({config_args}) }}}}\n\n{model.sql}"
    _safe_write(os.path.join(models_dir, f"{model.name}.sql"), sql)


def _safe_write(path: str, content: str) -> None:
    """Atomic write via .tmp → rename."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def remove_project(scope_id: str) -> None:
    """Remove the dbt project directory for an Org (called on Org delete)."""
    import shutil
    project_dir = _project_dir(scope_id)
    if os.path.isdir(project_dir):
        shutil.rmtree(project_dir)
        logger.info("remove_project: removed dbt project dir %s", project_dir)
