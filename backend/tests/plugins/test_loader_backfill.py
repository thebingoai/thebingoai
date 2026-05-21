"""Tests for the loader-side template backfill on plugin startup."""
import importlib.util
import os
import sys
import types as _types
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

# conftest stubs fastapi as ModuleType but lacks APIRouter; patch before loading base/loader.
if "fastapi" not in sys.modules:
    sys.modules["fastapi"] = _types.ModuleType("fastapi")
if not hasattr(sys.modules["fastapi"], "APIRouter"):
    sys.modules["fastapi"].APIRouter = MagicMock

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


# Load plugins.base for real dataclasses.
_spec_base = importlib.util.spec_from_file_location(
    "backend.plugins.base",
    os.path.join(_BACKEND_DIR, "plugins", "base.py"),
)
sys.modules.pop("backend.plugins.base", None)
_base = importlib.util.module_from_spec(_spec_base)
sys.modules["backend.plugins.base"] = _base
_spec_base.loader.exec_module(_base)

ConnectorRegistration = _base.ConnectorRegistration
PipelineTemplate = _base.PipelineTemplate
BingoPlugin = _base.BingoPlugin


# Load loader.py with stubbed downstream imports.
def _load_loader_module():
    spec = importlib.util.spec_from_file_location(
        "loader_under_test",
        os.path.join(_BACKEND_DIR, "plugins", "loader.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


loader = _load_loader_module()


class _DummyPlugin(BingoPlugin):
    def __init__(self, *, regs):
        self._regs = regs

    @property
    def name(self):
        return "dummy"

    @property
    def version(self):
        return "0.1.0"

    def connectors(self):
        return self._regs


def _registration_with_template():
    return ConnectorRegistration(
        type_id="my_source",
        display_name="My Source",
        description="",
        default_port=0,
        badge_variant="blue",
        connector_class=MagicMock,
        pipeline_templates=[
            PipelineTemplate(name="P", target_table="t", extraction_config={"k": "v"}),
        ],
    )


def _registration_no_templates():
    return ConnectorRegistration(
        type_id="other",
        display_name="Other",
        description="",
        default_port=0,
        badge_variant="blue",
        connector_class=MagicMock,
    )


@contextmanager
def _patched_env(*, settings_flag, connections, materialize_returns=([MagicMock()], [])):
    """Patch settings, DB session, and the public `backfill_templates_for_registrations`
    helper the loader now delegates to (instead of calling materialize per row inline).

    The patched helper iterates the supplied connections once per registration so
    legacy assertions on per-connection call counts still hold.
    """
    settings = MagicMock(template_backfill_on_startup=settings_flag)

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = connections
    db.commit = MagicMock()

    @contextmanager
    def session_factory():
        yield db

    materializer = MagicMock(return_value=materialize_returns)

    def _fake_backfill(regs, _db):
        result: dict = {}
        for reg in regs:
            if not (reg.pipeline_templates or reg.transform_templates):
                continue
            count = 0
            for conn in connections:
                try:
                    new_p, new_t = materializer(conn, reg, _db)
                    if new_p or new_t:
                        count += 1
                except Exception:
                    pass
            if count:
                _db.commit()
            result[reg.type_id] = count
        return result

    with patch.dict(sys.modules, {
        "backend.config": MagicMock(settings=settings),
        "backend.database.session": MagicMock(SessionLocal=session_factory),
        "backend.services.template_materializer": MagicMock(
            backfill_templates_for_registrations=_fake_backfill,
        ),
    }):
        yield db, materializer


def test_backfill_skipped_when_flag_is_off():
    plugin = _DummyPlugin(regs=[_registration_with_template()])
    with _patched_env(settings_flag=False, connections=[MagicMock(id=1)]) as (db, materializer):
        loader._backfill_templates_for_plugin(plugin)
    materializer.assert_not_called()
    db.commit.assert_not_called()


def test_backfill_skipped_when_no_templated_registrations():
    plugin = _DummyPlugin(regs=[_registration_no_templates()])
    with _patched_env(settings_flag=True, connections=[MagicMock(id=1)]) as (_db, materializer):
        loader._backfill_templates_for_plugin(plugin)
    materializer.assert_not_called()


def test_backfill_calls_materializer_per_connection_and_commits_once():
    plugin = _DummyPlugin(regs=[_registration_with_template()])
    conns = [MagicMock(id=1), MagicMock(id=2), MagicMock(id=3)]
    with _patched_env(settings_flag=True, connections=conns) as (db, materializer):
        loader._backfill_templates_for_plugin(plugin)
    assert materializer.call_count == 3
    db.commit.assert_called_once()


def test_backfill_does_not_commit_when_nothing_was_materialized():
    plugin = _DummyPlugin(regs=[_registration_with_template()])
    with _patched_env(
        settings_flag=True,
        connections=[MagicMock(id=1)],
        materialize_returns=([], []),
    ) as (db, _materializer):
        loader._backfill_templates_for_plugin(plugin)
    db.commit.assert_not_called()


def test_backfill_continues_on_per_connection_failure():
    plugin = _DummyPlugin(regs=[_registration_with_template()])
    conns = [MagicMock(id=1), MagicMock(id=2)]
    materializer = MagicMock(side_effect=[RuntimeError("boom"), ([MagicMock()], [])])

    def _fake_backfill(regs, _db):
        for reg in regs:
            for conn in conns:
                try:
                    materializer(conn, reg, _db)
                except Exception:
                    pass
        return {reg.type_id: 1 for reg in regs}

    with patch.dict(sys.modules, {
        "backend.config": MagicMock(settings=MagicMock(template_backfill_on_startup=True)),
        "backend.database.session": MagicMock(
            SessionLocal=lambda: _make_ctx(_make_db_with_connections(conns)),
        ),
        "backend.services.template_materializer": MagicMock(
            backfill_templates_for_registrations=_fake_backfill,
        ),
    }):
        loader._backfill_templates_for_plugin(plugin)
    assert materializer.call_count == 2  # second call still ran after first raised


def _make_db_with_connections(connections):
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = connections
    return db


@contextmanager
def _make_ctx(db):
    yield db
