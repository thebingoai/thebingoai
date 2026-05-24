from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Type, Callable, Union

from fastapi import APIRouter


@dataclass(frozen=True)
class PipelineTemplate:
    """Declarative pipeline a plugin ships per connector type.

    Materializes into a `pipelines` row at connection-create (and on plugin
    startup for pre-existing connections). Idempotent: dedup is by computed
    fingerprint via the existing `uq_pipeline_scope_fingerprint` constraint.

    `extraction_config` accepts either a static dict or a callable
    `(connection) -> dict` for per-connection values (e.g. workspace_id).

    `unique_key` names the natural-key columns that identify a row across
    snapshots. When set, the data plane registers a bronze external table
    over all `dt=*` partitions plus a silver VIEW that returns the latest
    snapshot per key — letting widgets see the full accumulated history
    instead of only the trailing lookback window. Leave None for sources
    that are pure overwrite (no per-row identity).
    """
    name: str
    target_table: Union[str, Callable[[Any], str]]
    extraction_config: Union[dict, Callable[[Any], dict]]
    cron: Optional[str] = None             # null = run-on-demand
    mode: Literal["full", "incremental"] = "full"
    incremental_key: Optional[str] = None
    unique_key: Optional[tuple[str, ...]] = None
    enabled: bool = True


@dataclass(frozen=True)
class TransformTemplate:
    """Declarative dbt model a plugin ships alongside its pipelines.

    Materializes into a `dbt_models` row. Dedup is by `(scope, name)` via the
    existing `uq_dbt_model_scope_name` constraint. `name` becomes the DataPlane
    table name; `sql` may reference Pipeline outputs via dbt source refs.
    """
    name: str
    sql: str
    materialization: Literal["table", "view", "incremental"] = "table"
    unique_key: Optional[str] = None
    cron: Optional[str] = None
    enabled: bool = True


@dataclass
class ConnectorRegistration:
    """Metadata + class for a connector type a plugin provides."""
    type_id: str
    display_name: str
    description: str
    default_port: int
    badge_variant: str
    connector_class: Type
    on_delete: Optional[Callable] = None
    on_test: Optional[Callable] = None
    on_refresh_schema: Optional[Callable] = None
    skip_schema_refresh: bool = False
    skip_profiling: bool = False
    sql_dialect_hint: Optional[str] = None
    # Connector-specific guidance the dashboard agent should follow when
    # designing dashboards against this connector's data (e.g. recommended
    # KPIs, common breakdowns, useful time-series). Injected into the
    # dashboard agent's system prompt for every connection of this type the
    # user has access to. Plain Markdown.
    dashboard_design_hint: Optional[str] = None
    version: Optional[str] = None
    card_meta_items: Optional[list[str]] = None
    # Phase 1: scope routing + dedup fingerprint
    default_scope_hint: Literal["user", "team", "org"] = "user"
    fingerprint: Optional[Callable] = None  # (DatabaseConnection) -> str | None
    extraction_config_model: Optional[Type] = None  # type[BaseModel] | None — P2.1 validation
    # Phase 3: post-run hook + legacy connector for migration window
    post_run: Optional[Callable] = None          # (connection, run) -> None — called after successful Pipeline run
    legacy_connector_class: Optional[Type] = None  # kept for migration window; replaced by connector_class
    # Plugin-template framework: declarative pipelines + transforms shipped with the connector.
    # Surface dlt_source_for here so all connectors use one form (vs the class-method-vs-module-level drift).
    # If None the runner falls back to `connector_class.dlt_source_for` for backward compatibility.
    dlt_source_for: Optional[Callable] = None    # (connection, extraction_config) -> dlt source
    pipeline_templates: Optional[list[PipelineTemplate]] = None
    transform_templates: Optional[list[TransformTemplate]] = None


class BingoPlugin(ABC):
    """Base class for all Bingo plugins."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @property
    def description(self) -> str:
        return ""

    @property
    def dependencies(self) -> list[str]:
        return []

    def connectors(self) -> list[ConnectorRegistration]:
        return []

    def api_routers(self) -> list[tuple[APIRouter, str]]:
        """Return (router, url_prefix) tuples."""
        return []

    def tool_builders(self) -> dict[str, Callable]:
        """Return {tool_name: builder_fn} for agent tools this plugin provides."""
        return {}

    def data_agent_tool_builders(self) -> dict[str, Callable]:
        """Return {tool_name: builder_fn} for tools that should be injected
        into the data agent's tool list (so SQL/analytics workflows can use
        them). Defaults to empty; only the connectors that own materialised
        pipelines need to add anything here. Each builder receives an
        AgentContext and returns a list of LangChain tools.
        """
        return {}

    def celery_task_modules(self) -> list[str]:
        """Return dotted module paths containing Celery tasks (e.g. ['myplugin.tasks'])."""
        return []

    def on_startup(self) -> None:
        pass

    def on_shutdown(self) -> None:
        pass

    async def on_chat_response(self, *, user_id: str, thread_id: str, user_message: str, assistant_message: str) -> None:
        """Called after a web chat response is persisted. Override to react."""
        pass
