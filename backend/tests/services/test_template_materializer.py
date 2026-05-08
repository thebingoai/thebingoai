"""Tests for template_materializer service."""
import importlib.util
import os
import sys
from unittest.mock import MagicMock

import pytest

# Stub heavy framework deps before importing plugins.base / template_materializer.
# conftest.py creates a ModuleType for fastapi but doesn't set APIRouter on it.
import types as _types
if "fastapi" not in sys.modules:
    sys.modules["fastapi"] = _types.ModuleType("fastapi")
if not hasattr(sys.modules["fastapi"], "APIRouter"):
    sys.modules["fastapi"].APIRouter = MagicMock

# sqlalchemy.exc isn't in conftest's stub hierarchy — add IntegrityError so the
# materializer's `from sqlalchemy.exc import IntegrityError` resolves.
if "sqlalchemy.exc" not in sys.modules:
    sys.modules["sqlalchemy.exc"] = _types.ModuleType("sqlalchemy.exc")
if not hasattr(sys.modules["sqlalchemy.exc"], "IntegrityError"):
    class _StubIntegrityError(Exception):
        pass
    sys.modules["sqlalchemy.exc"].IntegrityError = _StubIntegrityError

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


# Import target module directly to bypass app-level model imports.
spec = importlib.util.spec_from_file_location(
    "template_materializer",
    os.path.join(_BACKEND_DIR, "services", "template_materializer.py"),
)

# Stub the heavy backend imports the module performs at top-level.
_pipeline_module = MagicMock()
_pipeline_module.Pipeline = MagicMock(side_effect=lambda **kw: MagicMock(**kw))
_transforms_module = MagicMock()
_transforms_module.DbtModel = MagicMock(side_effect=lambda **kw: MagicMock(**kw))


def _fake_owner_scope(connection):
    s = MagicMock()
    s.kind = getattr(connection, "owner_scope_kind", None) or "user"
    s.id = getattr(connection, "owner_scope_id", None) or str(connection.user_id)
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


sys.modules["backend.models.pipeline"] = _pipeline_module
sys.modules["backend.models.transforms"] = _transforms_module
sys.modules["backend.data_plane.scope"] = _scope_module
sys.modules["backend.pipelines.runner"] = _runner_module

# Import the actual `plugins.base` (lightweight) so real dataclasses are used.
import importlib
sys.modules.pop("backend.plugins.base", None)
spec_base = importlib.util.spec_from_file_location(
    "backend.plugins.base",
    os.path.join(_BACKEND_DIR, "plugins", "base.py"),
)
base_module = importlib.util.module_from_spec(spec_base)
sys.modules["backend.plugins.base"] = base_module
spec_base.loader.exec_module(base_module)

ConnectorRegistration = base_module.ConnectorRegistration
PipelineTemplate = base_module.PipelineTemplate
TransformTemplate = base_module.TransformTemplate

template_materializer = importlib.util.module_from_spec(spec)
sys.modules["template_materializer"] = template_materializer
spec.loader.exec_module(template_materializer)

materialize_templates_for_connection = template_materializer.materialize_templates_for_connection


def _make_connection(conn_id=1, user_id="u1", db_type="my_source", scope_kind="user", scope_id="u1"):
    c = MagicMock()
    c.id = conn_id
    c.user_id = user_id
    c.db_type = db_type
    c.owner_scope_kind = scope_kind
    c.owner_scope_id = scope_id
    return c


def _make_db(existing_pipelines=None, existing_transforms=None):
    """A db.query(...).filter_by(...).first() chain that returns existing rows by lookup key."""
    db = MagicMock()
    pipeline_calls: list = []
    transform_calls: list = []

    def query(model):
        q = MagicMock()
        if model is _pipeline_module.Pipeline:
            def fb(**filters):
                pipeline_calls.append(filters)
                fp = filters.get("pipeline_fingerprint")
                hit = next((p for p in (existing_pipelines or []) if p.get("fp") == fp), None)
                f = MagicMock()
                f.first.return_value = MagicMock(**hit) if hit else None
                return f
            q.filter_by = MagicMock(side_effect=fb)
        else:
            def fb(**filters):
                transform_calls.append(filters)
                name = filters.get("name")
                hit = next((t for t in (existing_transforms or []) if t.get("name") == name), None)
                f = MagicMock()
                f.first.return_value = MagicMock(**hit) if hit else None
                return f
            q.filter_by = MagicMock(side_effect=fb)
        return q

    db.query = MagicMock(side_effect=query)
    db.add = MagicMock()
    db.flush = MagicMock()
    # Per-row savepoint pattern: db.begin_nested() returns a context with rollback().
    db.begin_nested = MagicMock(return_value=MagicMock())
    return db


def _registration(*, pipeline_templates=None, transform_templates=None, fingerprint=None):
    return ConnectorRegistration(
        type_id="my_source",
        display_name="My Source",
        description="",
        default_port=0,
        badge_variant="blue",
        connector_class=MagicMock,
        fingerprint=fingerprint,
        pipeline_templates=pipeline_templates,
        transform_templates=transform_templates,
    )


def test_materialize_creates_pipeline_with_static_config():
    reg = _registration(pipeline_templates=[
        PipelineTemplate(name="Daily", target_table="t1", extraction_config={"k": "v"}, cron="0 4 * * *"),
    ])
    conn = _make_connection()
    db = _make_db()

    new_p, new_t = materialize_templates_for_connection(conn, reg, db)

    assert len(new_p) == 1
    assert new_t == []
    # Per-row savepoint pattern: each insert begins a nested transaction.
    db.begin_nested.assert_called_once()


def test_materialize_resolves_callable_extraction_config():
    captured: dict = {}

    def cfg(connection):
        captured["called_with"] = connection.id
        return {"workspace_id": "ws-42"}

    reg = _registration(pipeline_templates=[
        PipelineTemplate(name="Pages", target_table="notion_pages", extraction_config=cfg),
    ])
    conn = _make_connection(conn_id=99)
    db = _make_db()

    new_p, _ = materialize_templates_for_connection(conn, reg, db)

    assert captured["called_with"] == 99
    assert len(new_p) == 1


def test_materialize_skips_when_pipeline_fingerprint_exists():
    config = {"k": "v"}
    fp = _fake_fingerprint(None, config)
    reg = _registration(pipeline_templates=[
        PipelineTemplate(name="Daily", target_table="t1", extraction_config=config),
    ])
    conn = _make_connection()
    db = _make_db(existing_pipelines=[{"fp": fp}])

    new_p, _ = materialize_templates_for_connection(conn, reg, db)

    assert new_p == []
    db.begin_nested.assert_not_called()  # SELECT-based dedup short-circuits before SAVEPOINT


def test_materialize_skips_when_dbt_model_name_exists():
    reg = _registration(transform_templates=[
        TransformTemplate(name="stg_t1", sql="select 1"),
    ])
    conn = _make_connection()
    db = _make_db(existing_transforms=[{"name": "stg_t1"}])

    _, new_t = materialize_templates_for_connection(conn, reg, db)

    assert new_t == []


def test_materialize_handles_both_kinds_in_single_call():
    reg = _registration(
        pipeline_templates=[PipelineTemplate(name="P", target_table="t", extraction_config={})],
        transform_templates=[TransformTemplate(name="stg_t", sql="select * from t")],
    )
    conn = _make_connection()
    db = _make_db()

    new_p, new_t = materialize_templates_for_connection(conn, reg, db)

    assert len(new_p) == 1
    assert len(new_t) == 1


def test_materialize_no_templates_is_noop():
    reg = _registration()
    conn = _make_connection()
    db = _make_db()

    new_p, new_t = materialize_templates_for_connection(conn, reg, db)

    assert new_p == []
    assert new_t == []
    db.begin_nested.assert_not_called()


def test_materialize_uses_connection_fingerprint_when_present():
    seen_fps: list = []

    def fp_fn(connection):
        return f"my_source:{connection.id}"

    def grab_fp(conn_fp, config):
        seen_fps.append(conn_fp)
        return _fake_fingerprint(conn_fp, config)

    _runner_module.compute_pipeline_fingerprint.side_effect = grab_fp

    try:
        reg = _registration(
            fingerprint=fp_fn,
            pipeline_templates=[PipelineTemplate(name="P", target_table="t", extraction_config={})],
        )
        conn = _make_connection(conn_id=7)
        db = _make_db()

        materialize_templates_for_connection(conn, reg, db)

        assert seen_fps == ["my_source:7"]
    finally:
        _runner_module.compute_pipeline_fingerprint.side_effect = _fake_fingerprint


def test_template_failure_does_not_break_subsequent_templates():
    bad = PipelineTemplate(name="Bad", target_table="t", extraction_config=lambda c: (_ for _ in ()).throw(RuntimeError("boom")))
    good = PipelineTemplate(name="Good", target_table="t2", extraction_config={"ok": True})
    reg = _registration(pipeline_templates=[bad, good])
    conn = _make_connection()
    db = _make_db()

    new_p, _ = materialize_templates_for_connection(conn, reg, db)

    assert len(new_p) == 1  # the good one still got through


def test_materialize_resolves_callable_target_table():
    captured: list = []

    def tt(connection):
        captured.append(connection.id)
        return f"notion_{connection.id}"

    reg = _registration(pipeline_templates=[
        PipelineTemplate(name="P", target_table=tt, extraction_config={}),
    ])
    conn = _make_connection(conn_id=42)
    db = _make_db()

    new_p, _ = materialize_templates_for_connection(conn, reg, db)

    assert captured == [42]
    assert len(new_p) == 1


def test_materialize_swallows_integrity_error_via_savepoint():
    """Concurrent backend + celery-worker startup can both pass SELECT dedup
    and race the INSERT. The savepoint pattern catches IntegrityError per row
    and treats it as 'another process won — skip'.
    """
    IntegrityError = sys.modules["sqlalchemy.exc"].IntegrityError

    reg = _registration(pipeline_templates=[
        PipelineTemplate(name="P", target_table="t", extraction_config={}),
    ])
    conn = _make_connection()
    db = _make_db()
    # flush() raises IntegrityError — simulating a concurrent INSERT.
    db.flush.side_effect = IntegrityError("uq_pipeline_scope_fingerprint", None, None)

    new_p, _ = materialize_templates_for_connection(conn, reg, db)

    assert new_p == []                                     # row treated as already existing
    db.begin_nested.return_value.rollback.assert_called()  # savepoint rolled back


def test_materialize_skips_when_connection_target_table_already_exists():
    """Secondary dedup: a Pipeline with the same (scope, source_connection_id, target_table)
    already exists (e.g. created by legacy registration code with a different fingerprint).
    """
    db = MagicMock()

    # Primary fingerprint check: returns None (no fingerprint match)
    # Secondary connection+target_table check: returns existing row
    call_state = {"primary_called": False}

    def query(model):
        q = MagicMock()
        def filter_by(**filters):
            f = MagicMock()
            if "pipeline_fingerprint" in filters:
                # Primary check: no match
                f.first.return_value = None
                call_state["primary_called"] = True
            elif "source_connection_id" in filters and "target_table" in filters:
                # Secondary check: HIT — existing legacy row
                f.first.return_value = MagicMock(id="legacy-pipeline")
            else:
                f.first.return_value = None
            return f
        q.filter_by = MagicMock(side_effect=filter_by)
        return q

    db.query = MagicMock(side_effect=query)
    db.add = MagicMock()
    db.flush = MagicMock()

    reg = _registration(pipeline_templates=[
        PipelineTemplate(name="P", target_table="legacy_table", extraction_config={}),
    ])
    conn = _make_connection()

    new_p, _ = materialize_templates_for_connection(conn, reg, db)

    assert call_state["primary_called"]   # primary check ran first
    assert new_p == []                     # secondary check caused skip
    db.add.assert_not_called()
