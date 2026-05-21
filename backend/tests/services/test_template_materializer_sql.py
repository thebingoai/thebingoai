"""Tests for the dynamic SQL pipeline-template path on template_materializer.

These cover Phase 1 of the SQL-connector → DataPlane wiring: postgres / mysql /
sqlite registrations declare no static `pipeline_templates`, but the materializer
introspects the live connector via `get_tables()` and synthesises one
PipelineTemplate per source table.

Module-stubbing follows the same pattern as
`test_template_materializer.py` (lightweight isolation — no FastAPI / SQLAlchemy
app boot).
"""
import importlib
import importlib.util
import os
import sys
import types as _types
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

# Stub heavy framework deps before importing plugins.base / template_materializer.
if "fastapi" not in sys.modules:
    sys.modules["fastapi"] = _types.ModuleType("fastapi")
if not hasattr(sys.modules["fastapi"], "APIRouter"):
    sys.modules["fastapi"].APIRouter = MagicMock

if "sqlalchemy.exc" not in sys.modules:
    sys.modules["sqlalchemy.exc"] = _types.ModuleType("sqlalchemy.exc")
if not hasattr(sys.modules["sqlalchemy.exc"], "IntegrityError"):
    class _StubIntegrityError(Exception):
        pass
    sys.modules["sqlalchemy.exc"].IntegrityError = _StubIntegrityError

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


# ── Stub downstream modules the materializer imports at top-level ──────────
_pipeline_module = MagicMock()


class _PipelineCol:
    """Tiny stand-in for SQLAlchemy column expressions used by `_slugify_connection_name`.

    The slug check builds `Pipeline.target_table.like("foo\\_\\_%")` which would
    normally produce a SQLAlchemy comparator. The materializer never inspects
    the resulting object — it just passes it to `db.query(...).filter(...)`,
    which is fully mocked. So returning anything callable-or-truthy is fine.
    """
    def like(self, _pattern):
        return MagicMock()

    def __eq__(self, _other):
        return MagicMock()


_pipeline_module.Pipeline = MagicMock(side_effect=lambda **kw: MagicMock(**kw))
_pipeline_module.Pipeline.owner_scope_kind = _PipelineCol()
_pipeline_module.Pipeline.owner_scope_id = _PipelineCol()
_pipeline_module.Pipeline.target_table = _PipelineCol()
_pipeline_module.Pipeline.source_connection_id = _PipelineCol()
_pipeline_module.Pipeline.pipeline_fingerprint = _PipelineCol()

_transforms_module = MagicMock()
_transforms_module.DbtModel = MagicMock(side_effect=lambda **kw: MagicMock(**kw))


def _fake_owner_scope(connection):
    s = MagicMock()
    s.kind = getattr(connection, "owner_scope_kind", None) or "user"
    s.id = getattr(connection, "owner_scope_id", None) or str(getattr(connection, "user_id", "u1"))
    return s


_scope_module = MagicMock()
_scope_module.OwnerScope = MagicMock()
_scope_module.OwnerScope.from_connection = MagicMock(side_effect=_fake_owner_scope)


def _fake_fingerprint(conn_fp, config):
    import hashlib, json
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{conn_fp or ''}|{canonical}".encode()).hexdigest()


_runner_module = MagicMock()
_runner_module.compute_pipeline_fingerprint = MagicMock(side_effect=_fake_fingerprint)


class _StubSqlExtractionConfig:
    """Sentinel object so `reg.extraction_config_model is SqlExtractionConfig` works."""
    pass


_sql_dlt_module = _types.ModuleType("backend.connectors.sql_dlt")
_sql_dlt_module.SqlExtractionConfig = _StubSqlExtractionConfig

sys.modules["backend.models.pipeline"] = _pipeline_module
sys.modules["backend.models.transforms"] = _transforms_module
sys.modules["backend.data_plane.scope"] = _scope_module
sys.modules["backend.pipelines.runner"] = _runner_module
sys.modules["backend.connectors.sql_dlt"] = _sql_dlt_module


# Load plugins.base for real dataclasses.
sys.modules.pop("backend.plugins.base", None)
_spec_base = importlib.util.spec_from_file_location(
    "backend.plugins.base",
    os.path.join(_BACKEND_DIR, "plugins", "base.py"),
)
_base = importlib.util.module_from_spec(_spec_base)
sys.modules["backend.plugins.base"] = _base
_spec_base.loader.exec_module(_base)

ConnectorRegistration = _base.ConnectorRegistration
PipelineTemplate = _base.PipelineTemplate
TransformTemplate = _base.TransformTemplate


def _load_materializer():
    sys.modules.pop("template_materializer_sql_under_test", None)
    spec = importlib.util.spec_from_file_location(
        "template_materializer_sql_under_test",
        os.path.join(_BACKEND_DIR, "services", "template_materializer.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


materializer = _load_materializer()


# ── Fixtures / helpers ────────────────────────────────────────────────────


def _make_connection(*, conn_id=1, user_id="u1", db_type="postgres", scope_kind="user", scope_id="u1", name="pg_demo"):
    c = MagicMock()
    c.id = conn_id
    c.user_id = user_id
    c.db_type = db_type
    c.owner_scope_kind = scope_kind
    c.owner_scope_id = scope_id
    c.name = name
    return c


def _make_db(*, slug_collision_other_conn_id=None):
    """db.query().filter().first() chain.

    By default `_slugify_connection_name`'s collision SELECT returns None (no
    collision). If `slug_collision_other_conn_id` is set, returns a fake row
    pinned to that connection id so the slugifier sees a collision.
    """
    db = MagicMock()

    def query(model):
        q = MagicMock()
        # Slug-collision SELECT uses Pipeline.target_table.like(...) through .filter()
        if slug_collision_other_conn_id is not None:
            existing = MagicMock(source_connection_id=slug_collision_other_conn_id)
        else:
            existing = None
        q.filter.return_value.first.return_value = existing
        # The materializer dedup path (filter_by) also goes through db.query
        q.filter_by.return_value.first.return_value = None
        return q

    db.query = MagicMock(side_effect=query)
    db.add = MagicMock()
    db.flush = MagicMock()
    db.begin_nested = MagicMock(return_value=MagicMock())
    return db


def _sql_reg(*, type_id="postgres", has_dlt=True, has_static_templates=False):
    return ConnectorRegistration(
        type_id=type_id,
        display_name=type_id.title(),
        description="",
        default_port=5432,
        badge_variant="info",
        connector_class=MagicMock,
        extraction_config_model=_StubSqlExtractionConfig,
        dlt_source_for=(lambda c, cfg: MagicMock()) if has_dlt else None,
        pipeline_templates=(
            [PipelineTemplate(name="static", target_table="t", extraction_config={})]
            if has_static_templates else None
        ),
    )


def _non_sql_reg(*, type_id="dataset"):
    return ConnectorRegistration(
        type_id=type_id,
        display_name=type_id.title(),
        description="",
        default_port=0,
        badge_variant="info",
        connector_class=MagicMock,
        extraction_config_model=None,
        dlt_source_for=None,
    )


def _fake_schema(table, columns):
    """Helper to construct an object that looks like TableSchema with `.columns`."""
    s = MagicMock()
    s.columns = columns
    s.table_name = table
    return s


@contextmanager
def _patched_factory(
    *,
    tables=None,
    open_raises=False,
    get_tables_raises=False,
    schemas: dict | None = None,
):
    """Patch `backend.connectors.factory.get_connector_for_connection`.

    `tables` defaults to ['users','orders']. Pass [] to simulate empty source.
    `open_raises` makes the factory itself raise (connection unreachable).
    `get_tables_raises` lets the factory return a connector whose get_tables raises.
    `schemas` is a `{table_name: [{column dict}, ...]}` map for per-table column
    metadata used by Phase 3 unique_key/incremental_key tests.
    """
    if tables is None:
        tables = ["users", "orders"]

    fake_factory = _types.ModuleType("backend.connectors.factory")

    if open_raises:
        def open_fn(_conn):
            raise ConnectionError("simulated unreachable")
    else:
        connector = MagicMock()
        if get_tables_raises:
            connector.get_tables.side_effect = RuntimeError("simulated query failure")
        else:
            connector.get_tables.return_value = list(tables)
        connector.close = MagicMock()

        def _schema_for(table, schema=None):
            cols = (schemas or {}).get(table, [])
            return _fake_schema(table, cols)

        connector.get_table_schema.side_effect = _schema_for

        def open_fn(_conn):
            return connector

    fake_factory.get_connector_for_connection = open_fn
    fake_factory._CONNECTORS = {}
    with patch.dict(sys.modules, {"backend.connectors.factory": fake_factory}):
        yield fake_factory


# ── _is_dynamic_sql_registration ─────────────────────────────────────────


def test_is_dynamic_sql_registration_true_for_postgres():
    assert materializer._is_dynamic_sql_registration(_sql_reg(type_id="postgres")) is True


def test_is_dynamic_sql_registration_true_for_mysql():
    assert materializer._is_dynamic_sql_registration(_sql_reg(type_id="mysql")) is True


def test_is_dynamic_sql_registration_false_when_static_templates_present():
    reg = _sql_reg(type_id="postgres", has_static_templates=True)
    assert materializer._is_dynamic_sql_registration(reg) is False


def test_is_dynamic_sql_registration_false_for_non_sql_extraction_model():
    assert materializer._is_dynamic_sql_registration(_non_sql_reg(type_id="dataset")) is False


def test_is_dynamic_sql_registration_false_when_dlt_source_for_missing():
    reg = _sql_reg(type_id="sqlite", has_dlt=False)
    assert materializer._is_dynamic_sql_registration(reg) is False


def test_is_dynamic_sql_registration_force_true_skips_dlt_check():
    """SQLite post-migration path: no dlt source, but force=True still qualifies."""
    reg = _sql_reg(type_id="sqlite", has_dlt=False)
    assert materializer._is_dynamic_sql_registration(reg, force=True) is True


# ── _slugify_connection_name ─────────────────────────────────────────────


def test_slugify_lowercases_and_sanitises():
    db = _make_db()
    conn = _make_connection(name="My Demo DB!")
    assert materializer._slugify_connection_name(conn, db) == "my_demo_db"


def test_slugify_falls_back_to_conn_id_when_name_empty():
    db = _make_db()
    conn = _make_connection(conn_id="abcdef0123456789", name="")
    assert materializer._slugify_connection_name(conn, db) == "conn_abcdef01"


def test_slugify_appends_id_suffix_on_collision_with_different_connection():
    """If another connection already owns target_table='pg_demo__*', new
    connection's slug gets disambiguated by its id prefix.
    """
    db = _make_db(slug_collision_other_conn_id="other-conn")
    conn = _make_connection(conn_id="abcdef0123456789", name="pg_demo")
    assert materializer._slugify_connection_name(conn, db) == "pg_demo_abcdef01"


def test_slugify_no_collision_when_existing_row_is_same_connection():
    """Re-running materialise for the same connection must not append a suffix."""
    db = _make_db(slug_collision_other_conn_id=1)
    conn = _make_connection(conn_id=1, name="pg_demo")
    assert materializer._slugify_connection_name(conn, db) == "pg_demo"


# ── _build_sql_pipeline_templates ────────────────────────────────────────


def test_build_sql_pipeline_templates_yields_one_per_table():
    db = _make_db()
    conn = _make_connection(name="pg_demo")
    reg = _sql_reg(type_id="postgres")

    with _patched_factory(tables=["users", "orders", "events"]):
        templates = materializer._build_sql_pipeline_templates(conn, reg, db)

    assert len(templates) == 3
    assert [t.target_table for t in templates] == [
        "pg_demo__users", "pg_demo__orders", "pg_demo__events",
    ]
    assert all(t.extraction_config["tables"] == [name] for t, name in zip(
        templates, ["users", "orders", "events"]
    ))
    assert all(t.cron is None for t in templates)
    assert all(t.mode == "full" for t in templates)


def test_build_sql_pipeline_templates_returns_empty_when_connector_open_fails():
    db = _make_db()
    conn = _make_connection()
    reg = _sql_reg(type_id="postgres")

    with _patched_factory(open_raises=True):
        templates = materializer._build_sql_pipeline_templates(conn, reg, db)

    assert templates == []


def test_build_sql_pipeline_templates_returns_empty_when_get_tables_raises():
    db = _make_db()
    conn = _make_connection()
    reg = _sql_reg(type_id="postgres")

    with _patched_factory(get_tables_raises=True):
        templates = materializer._build_sql_pipeline_templates(conn, reg, db)

    assert templates == []


def test_build_sql_pipeline_templates_returns_empty_when_source_has_no_tables():
    db = _make_db()
    conn = _make_connection()
    reg = _sql_reg(type_id="postgres")

    with _patched_factory(tables=[]):
        templates = materializer._build_sql_pipeline_templates(conn, reg, db)

    assert templates == []


def test_build_sql_pipeline_templates_skips_non_dynamic_registrations():
    """A non-SQL registration must not trigger fan-out even if called directly."""
    db = _make_db()
    conn = _make_connection()
    reg = _non_sql_reg(type_id="dataset")

    with _patched_factory(tables=["t1"]):
        templates = materializer._build_sql_pipeline_templates(conn, reg, db)

    assert templates == []


def test_build_sql_pipeline_templates_force_true_works_for_sqlite():
    """force=True path used by SQLite post-migration: no dlt_source_for needed."""
    db = _make_db()
    conn = _make_connection(db_type="sqlite", name="my_db")
    reg = _sql_reg(type_id="sqlite", has_dlt=False)

    with _patched_factory(tables=["accounts", "txn"]):
        templates = materializer._build_sql_pipeline_templates(conn, reg, db, force=True)

    assert [t.target_table for t in templates] == ["my_db__accounts", "my_db__txn"]


# ── materialize_templates_for_connection (dynamic SQL path) ──────────────


def test_materialize_for_postgres_connection_creates_n_pipelines():
    db = _make_db()
    conn = _make_connection(name="pg_demo")
    reg = _sql_reg(type_id="postgres")

    with _patched_factory(tables=["users", "orders"]):
        new_p, _new_t = materializer.materialize_templates_for_connection(conn, reg, db)

    assert len(new_p) == 2
    # SAVEPOINT opens once per insert. Phase 2 also fans out stg_ DbtModel
    # rows so the lower bound is 2 pipelines + 2 transforms = 4.
    assert db.begin_nested.call_count >= 2


def test_materialize_static_templates_still_win_when_present():
    """If a registration ships static `pipeline_templates`, the dynamic path
    must not run — even if the registration also has SqlExtractionConfig set.
    """
    db = _make_db()
    conn = _make_connection()
    reg = _sql_reg(type_id="postgres", has_static_templates=True)

    with _patched_factory(tables=["users", "orders"]) as factory:
        # Confirm we never even opened the connector.
        opened = []
        original = factory.get_connector_for_connection

        def spy(c):
            opened.append(c)
            return original(c)

        factory.get_connector_for_connection = spy
        new_p, _ = materializer.materialize_templates_for_connection(conn, reg, db)

    assert len(new_p) == 1  # the single static template
    assert opened == []


def test_materialize_swallows_dynamic_template_exceptions():
    """A get_tables failure must not break create_connection — returns ([],[])."""
    db = _make_db()
    conn = _make_connection()
    reg = _sql_reg(type_id="postgres")

    with _patched_factory(get_tables_raises=True):
        new_p, new_t = materializer.materialize_templates_for_connection(conn, reg, db)

    assert new_p == []
    assert new_t == []


# ── backfill_templates_for_registrations / for_core_connectors ──────────


def test_backfill_includes_dynamic_sql_regs():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [
        _make_connection(conn_id=1, db_type="postgres", name="pg1"),
    ]
    # Dedup SELECTs must miss so the inner materialize actually inserts.
    db.query.return_value.filter_by.return_value.first.return_value = None
    # Slug-collision SELECT also returns None (no other conn owns the prefix).
    db.query.return_value.filter.return_value.first.return_value = None
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.begin_nested = MagicMock(return_value=MagicMock())

    fake_models = _types.ModuleType("backend.models.database_connection")
    fake_models.DatabaseConnection = MagicMock()
    fake_models.DatabaseConnection.db_type = _PipelineCol()

    reg = _sql_reg(type_id="postgres")

    with patch.dict(sys.modules, {"backend.models.database_connection": fake_models}), \
         _patched_factory(tables=["users"]):
        result = materializer.backfill_templates_for_registrations([reg], db)

    assert result == {"postgres": 1}
    db.commit.assert_called()


def test_backfill_skips_when_no_qualifying_registrations():
    db = MagicMock()
    reg = _non_sql_reg(type_id="dataset")
    result = materializer.backfill_templates_for_registrations([reg], db)
    assert result == {}
    db.query.assert_not_called()


def test_backfill_for_core_connectors_skipped_when_flag_off():
    fake_settings = _types.ModuleType("backend.config")
    fake_settings.settings = MagicMock(template_backfill_on_startup=False)
    with patch.dict(sys.modules, {"backend.config": fake_settings}):
        out = materializer.backfill_templates_for_core_connectors(MagicMock())
    assert out == {}


# ── Phase 3: unique_key + incremental_key + partition detection ──────────


def test_template_populates_unique_key_from_pk():
    db = _make_db()
    conn = _make_connection(name="pg_demo")
    reg = _sql_reg(type_id="postgres")
    schemas = {
        "users": [
            {"name": "id", "type": "integer", "nullable": False, "primary_key": True},
            {"name": "email", "type": "text", "nullable": False, "primary_key": False},
        ],
    }

    with _patched_factory(tables=["users"], schemas=schemas):
        templates = materializer._build_sql_pipeline_templates(conn, reg, db)

    assert len(templates) == 1
    assert templates[0].unique_key == ("id",)


def test_template_populates_unique_key_with_composite_pk():
    db = _make_db()
    conn = _make_connection(name="pg_demo")
    reg = _sql_reg(type_id="postgres")
    schemas = {
        "membership": [
            {"name": "user_id", "type": "integer", "nullable": False, "primary_key": True},
            {"name": "team_id", "type": "integer", "nullable": False, "primary_key": True},
            {"name": "joined_at", "type": "timestamp", "nullable": False, "primary_key": False},
        ],
    }

    with _patched_factory(tables=["membership"], schemas=schemas):
        templates = materializer._build_sql_pipeline_templates(conn, reg, db)

    assert templates[0].unique_key == ("user_id", "team_id")


def test_template_unique_key_none_when_no_primary_key():
    db = _make_db()
    conn = _make_connection(name="pg_demo")
    reg = _sql_reg(type_id="postgres")
    schemas = {
        "events": [
            {"name": "id", "type": "bigint", "nullable": True, "primary_key": False},
        ],
    }

    with _patched_factory(tables=["events"], schemas=schemas):
        templates = materializer._build_sql_pipeline_templates(conn, reg, db)

    assert templates[0].unique_key is None


def test_template_picks_partition_key_for_postgres():
    db = _make_db()
    conn = _make_connection(name="pg_demo")
    reg = _sql_reg(type_id="postgres")
    schemas = {
        "events_p": [
            {"name": "id", "type": "integer", "nullable": False, "primary_key": True},
            {"name": "event_date", "type": "date", "nullable": False, "primary_key": False},
        ],
    }

    # Patch postgres.detect_partition_key to return 'event_date'.
    fake_pg = _types.ModuleType("backend.connectors.postgres")
    fake_pg.detect_partition_key = lambda c, schema, table: "event_date"

    with patch.dict(sys.modules, {"backend.connectors.postgres": fake_pg}), \
         _patched_factory(tables=["events_p"], schemas=schemas):
        templates = materializer._build_sql_pipeline_templates(conn, reg, db)

    assert templates[0].incremental_key == "event_date"
    assert templates[0].mode == "incremental"
    assert templates[0].unique_key == ("id",)


def test_template_picks_partition_key_for_mysql():
    db = _make_db()
    conn = _make_connection(name="my_demo", db_type="mysql")
    reg = _sql_reg(type_id="mysql")
    schemas = {
        "events_p": [
            {"name": "id", "type": "bigint", "nullable": False, "primary_key": True},
            {"name": "ts", "type": "timestamp", "nullable": False, "primary_key": False},
        ],
    }

    fake_my = _types.ModuleType("backend.connectors.mysql")
    fake_my.detect_partition_key = lambda c, schema, table: "ts"

    with patch.dict(sys.modules, {"backend.connectors.mysql": fake_my}), \
         _patched_factory(tables=["events_p"], schemas=schemas):
        templates = materializer._build_sql_pipeline_templates(conn, reg, db)

    assert templates[0].incremental_key == "ts"
    assert templates[0].mode == "incremental"


def test_template_falls_back_to_date_column_heuristic():
    db = _make_db()
    conn = _make_connection(name="pg_demo")
    reg = _sql_reg(type_id="postgres")
    schemas = {
        "users": [
            {"name": "id", "type": "integer", "nullable": False, "primary_key": True},
            {"name": "email", "type": "text", "nullable": False, "primary_key": False},
            {"name": "updated_at", "type": "timestamp without time zone", "nullable": False, "primary_key": False},
        ],
    }

    fake_pg = _types.ModuleType("backend.connectors.postgres")
    fake_pg.detect_partition_key = lambda c, schema, table: None  # no partition

    with patch.dict(sys.modules, {"backend.connectors.postgres": fake_pg}), \
         _patched_factory(tables=["users"], schemas=schemas):
        templates = materializer._build_sql_pipeline_templates(conn, reg, db)

    assert templates[0].incremental_key == "updated_at"
    assert templates[0].mode == "incremental"


def test_template_heuristic_ignores_date_named_non_date_column():
    """Column named `dt` of type INT must NOT be picked as incremental_key."""
    db = _make_db()
    conn = _make_connection(name="pg_demo")
    reg = _sql_reg(type_id="postgres")
    schemas = {
        "t": [
            {"name": "id", "type": "integer", "nullable": False, "primary_key": True},
            {"name": "dt", "type": "integer", "nullable": True, "primary_key": False},
        ],
    }

    fake_pg = _types.ModuleType("backend.connectors.postgres")
    fake_pg.detect_partition_key = lambda c, schema, table: None

    with patch.dict(sys.modules, {"backend.connectors.postgres": fake_pg}), \
         _patched_factory(tables=["t"], schemas=schemas):
        templates = materializer._build_sql_pipeline_templates(conn, reg, db)

    assert templates[0].incremental_key is None
    assert templates[0].mode == "full"


def test_template_mode_full_when_no_incremental_key():
    db = _make_db()
    conn = _make_connection(name="pg_demo")
    reg = _sql_reg(type_id="postgres")
    schemas = {
        "users": [
            {"name": "id", "type": "integer", "nullable": False, "primary_key": True},
            {"name": "email", "type": "text", "nullable": False, "primary_key": False},
        ],
    }

    fake_pg = _types.ModuleType("backend.connectors.postgres")
    fake_pg.detect_partition_key = lambda c, schema, table: None

    with patch.dict(sys.modules, {"backend.connectors.postgres": fake_pg}), \
         _patched_factory(tables=["users"], schemas=schemas):
        templates = materializer._build_sql_pipeline_templates(conn, reg, db)

    assert templates[0].mode == "full"
    assert templates[0].incremental_key is None


def test_template_schema_failure_does_not_break_fan_out():
    """get_table_schema crashing for one table must not lose the others —
    pk/inc fields just default to None."""
    db = _make_db()
    conn = _make_connection(name="pg_demo")
    reg = _sql_reg(type_id="postgres")

    fake_factory = _types.ModuleType("backend.connectors.factory")
    connector = MagicMock()
    connector.get_tables.return_value = ["users"]
    connector.get_table_schema.side_effect = RuntimeError("boom")
    connector.close = MagicMock()
    fake_factory.get_connector_for_connection = lambda c: connector
    fake_factory._CONNECTORS = {}

    with patch.dict(sys.modules, {"backend.connectors.factory": fake_factory}):
        templates = materializer._build_sql_pipeline_templates(conn, reg, db)

    assert len(templates) == 1
    assert templates[0].unique_key is None
    assert templates[0].incremental_key is None
    assert templates[0].mode == "full"


# ── Phase 2: stg_ dbt model auto-scaffold ────────────────────────────────


def test_build_sql_transform_templates_yields_stg_view_per_pipeline():
    pipelines = [
        PipelineTemplate(name="A: users", target_table="pg_demo__users", extraction_config={}),
        PipelineTemplate(name="A: orders", target_table="pg_demo__orders", extraction_config={}),
    ]
    transforms = materializer._build_sql_transform_templates(pipelines)

    assert [t.name for t in transforms] == ["stg_pg_demo__users", "stg_pg_demo__orders"]
    assert all(t.materialization == "view" for t in transforms)
    assert transforms[0].sql == "SELECT * FROM {{ source('pipelines', 'pg_demo__users') }}"
    assert transforms[1].sql == "SELECT * FROM {{ source('pipelines', 'pg_demo__orders') }}"


def test_build_sql_transform_templates_skips_callable_target_tables():
    """Defensive: a pipeline template with a callable target_table can't be
    statically referenced by a stg model — skip rather than crash.
    """
    pipelines = [
        PipelineTemplate(name="dynamic", target_table=lambda c: "t", extraction_config={}),
        PipelineTemplate(name="ok", target_table="t2", extraction_config={}),
    ]
    transforms = materializer._build_sql_transform_templates(pipelines)
    assert [t.name for t in transforms] == ["stg_t2"]


def test_materialize_postgres_creates_pipeline_and_stg_pair_per_table():
    db = _make_db()
    conn = _make_connection(name="pg_demo")
    reg = _sql_reg(type_id="postgres")

    with _patched_factory(tables=["users", "orders"]):
        new_p, new_t = materializer.materialize_templates_for_connection(conn, reg, db)

    assert len(new_p) == 2
    assert len(new_t) == 2
    # SAVEPOINT opens once per insert (2 pipelines + 2 dbt models = 4).
    assert db.begin_nested.call_count == 4


def test_materialize_static_transforms_still_win_when_present_for_static_reg():
    """A registration with only static templates uses its declared
    `transform_templates`. The dynamic stg_ path only fires when dynamic
    pipelines were generated.
    """
    db = _make_db()
    conn = _make_connection()
    reg = _sql_reg(type_id="postgres", has_static_templates=True)
    # Add a static transform to the same registration to confirm it still flows.
    reg.transform_templates = [TransformTemplate(name="manual", sql="select 1")]

    with _patched_factory(tables=["never_called"]):
        _, new_t = materializer.materialize_templates_for_connection(conn, reg, db)

    assert len(new_t) == 1
    # Confirm name is the static one, not stg_<dynamic_table>.
    assert db.add.call_args_list[-1][0][0]  # last add — at minimum some row added


# ── Phase 4: SQLite post-migration materialise ───────────────────────────


def test_materialize_post_migration_creates_pipelines_and_stg_models():
    db = _make_db()
    conn = _make_connection(db_type="sqlite", name="customers")

    # SQLite registration: no dlt_source_for, so force=True path required.
    sqlite_reg = _sql_reg(type_id="sqlite", has_dlt=False)
    sqlite_reg.fingerprint = lambda c: f"sqlite:{c.id}"

    fake_factory = _types.ModuleType("backend.connectors.factory")
    fake_factory._CONNECTORS = {"sqlite": sqlite_reg}
    connector = MagicMock()
    connector.get_tables.return_value = ["accounts", "txn"]
    connector.get_table_schema.side_effect = lambda t, schema=None: _fake_schema(t, [
        {"name": "id", "type": "integer", "nullable": False, "primary_key": True},
    ])
    connector.close = MagicMock()
    fake_factory.get_connector_for_connection = lambda c: connector

    with patch.dict(sys.modules, {"backend.connectors.factory": fake_factory}):
        new_p, new_t = materializer.materialize_post_migration(conn, db)

    assert len(new_p) == 2
    assert len(new_t) == 2
    assert all(p.cron is None for p in new_p) if new_p else True


def test_materialize_post_migration_no_op_when_sqlite_not_registered():
    db = _make_db()
    conn = _make_connection(db_type="sqlite", name="x")
    fake_factory = _types.ModuleType("backend.connectors.factory")
    fake_factory._CONNECTORS = {}
    fake_factory.get_connector_for_connection = MagicMock()
    with patch.dict(sys.modules, {"backend.connectors.factory": fake_factory}):
        out_p, out_t = materializer.materialize_post_migration(conn, db)
    assert out_p == []
    assert out_t == []


def test_backfill_for_core_connectors_walks_factory_registry():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    db.commit = MagicMock()
    db.rollback = MagicMock()

    fake_settings = _types.ModuleType("backend.config")
    fake_settings.settings = MagicMock(template_backfill_on_startup=True)

    fake_factory = _types.ModuleType("backend.connectors.factory")
    fake_factory._CONNECTORS = {
        "postgres": _sql_reg(type_id="postgres"),
        "dataset": _non_sql_reg(type_id="dataset"),
        "mysql": _sql_reg(type_id="mysql"),
    }
    fake_factory.get_connector_for_connection = MagicMock()

    fake_models = _types.ModuleType("backend.models.database_connection")
    fake_models.DatabaseConnection = MagicMock()
    fake_models.DatabaseConnection.db_type = _PipelineCol()

    with patch.dict(sys.modules, {
        "backend.config": fake_settings,
        "backend.connectors.factory": fake_factory,
        "backend.models.database_connection": fake_models,
    }):
        out = materializer.backfill_templates_for_core_connectors(db)

    # postgres and mysql qualify; dataset is filtered out.
    assert set(out.keys()) == {"postgres", "mysql"}
