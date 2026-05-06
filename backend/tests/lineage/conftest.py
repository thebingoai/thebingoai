"""Local conftest for lineage tests.

Mirrors tests/transforms/conftest.py: stubs SQLAlchemy-heavy modules so
the lineage service / cache / api modules can import under the lightweight
test environment.
"""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock


def _stub_backend_database():
    class _Base:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class _TimestampMixin:
        created_at = None
        updated_at = None

    db_base_mod = ModuleType("backend.database.base")
    db_base_mod.Base = _Base
    db_base_mod.TimestampMixin = _TimestampMixin
    sys.modules.setdefault("backend.database.base", db_base_mod)

    db_session_mod = ModuleType("backend.database.session")
    db_session_mod.SessionLocal = MagicMock()
    db_session_mod.engine = MagicMock()
    db_session_mod.get_db = MagicMock()
    sys.modules.setdefault("backend.database.session", db_session_mod)

    db_mod = ModuleType("backend.database")
    db_mod.Base = _Base
    db_mod.TimestampMixin = _TimestampMixin
    db_mod.engine = MagicMock()
    db_mod.SessionLocal = MagicMock()
    db_mod.get_db = MagicMock()
    db_mod.base = db_base_mod
    sys.modules.setdefault("backend.database", db_mod)


_stub_backend_database()


def _stub_models():
    db_base_mod = sys.modules["backend.database.base"]
    _Base = db_base_mod.Base
    _TimestampMixin = db_base_mod.TimestampMixin

    # Class attributes are needed because lineage/service.py builds queries like
    # Pipeline.owner_scope_kind == scope.kind which reads attributes off the
    # class. The fake db.query() ignores filter args, so any object that
    # supports __eq__ is fine.
    class _Field:
        def __eq__(self, _): return True
        def __ne__(self, _): return False
        def isnot(self, _): return True
        def desc(self): return self
        def asc(self): return self

    class Pipeline(_Base, _TimestampMixin):
        __tablename__ = "pipelines"
        owner_scope_kind = _Field()
        owner_scope_id = _Field()
        target_table = _Field()
        id = _Field()
    class PipelineRun(_Base):
        __tablename__ = "pipeline_runs"
        pipeline_id = _Field()
        started_at = _Field()
    class DltPipelineState(_Base):
        __tablename__ = "dlt_pipeline_states"
    class DbtModel(_Base, _TimestampMixin):
        __tablename__ = "dbt_models"
        owner_scope_kind = _Field()
        owner_scope_id = _Field()
        name = _Field()
    class DbtRun(_Base):
        __tablename__ = "dbt_runs"
        owner_scope_kind = _Field()
        owner_scope_id = _Field()
        started_at = _Field()
        manifest_blob = _Field()
    class Dashboard(_Base, _TimestampMixin):
        __tablename__ = "dashboards"
        widgets = []
        user_id = _Field()
    class WidgetPendingManualRewrite(_Base):
        __tablename__ = "widgets_pending_manual_rewrite"
        widget_id = _Field()
        status = _Field()

    pipe_mod = ModuleType("backend.models.pipeline")
    pipe_mod.Pipeline = Pipeline
    pipe_mod.PipelineRun = PipelineRun
    pipe_mod.DltPipelineState = DltPipelineState
    sys.modules["backend.models.pipeline"] = pipe_mod

    tx_mod = ModuleType("backend.models.transforms")
    tx_mod.DbtModel = DbtModel
    tx_mod.DbtRun = DbtRun
    sys.modules["backend.models.transforms"] = tx_mod

    dash_mod = ModuleType("backend.models.dashboard")
    dash_mod.Dashboard = Dashboard
    sys.modules["backend.models.dashboard"] = dash_mod

    sub_mod = ModuleType("backend.migration.substrate")
    sub_mod.WidgetPendingManualRewrite = WidgetPendingManualRewrite
    sys.modules["backend.migration.substrate"] = sub_mod
    sys.modules.setdefault("backend.migration", ModuleType("backend.migration"))

    # Ensure backend.models package exists (without running its real __init__)
    if "backend.models" not in sys.modules:
        sys.modules["backend.models"] = ModuleType("backend.models")


_stub_models()


def _stub_misc():
    # Avoid loading the real config (which reads .env)
    if "backend.config" not in sys.modules:
        cfg = ModuleType("backend.config")
        cfg.settings = type("S", (), {"redis_url": "redis://localhost:6379/0"})()
        sys.modules["backend.config"] = cfg

    # Stub backend.data_plane.scope directly so importing it doesn't cascade
    # through backend.data_plane.__init__ → connectors → psycopg2.
    if "backend.data_plane" not in sys.modules:
        sys.modules["backend.data_plane"] = ModuleType("backend.data_plane")
    if "backend.data_plane.scope" not in sys.modules:
        scope_mod = ModuleType("backend.data_plane.scope")

        class OwnerScope:
            def __init__(self, kind, id):
                self.kind = kind
                self.id = str(id)
            def as_path(self):
                return f"{self.kind}/{self.id}"
            def __eq__(self, other):
                return isinstance(other, OwnerScope) and self.kind == other.kind and self.id == other.id
            def __hash__(self):
                return hash((self.kind, self.id))

        scope_mod.OwnerScope = OwnerScope
        sys.modules["backend.data_plane.scope"] = scope_mod

    # Ensure flag_modified is importable from sqlalchemy.orm.attributes
    sa_mod = sys.modules.get("sqlalchemy")
    if sa_mod is not None and not hasattr(sa_mod, "orm"):
        orm_mod = ModuleType("sqlalchemy.orm")
        sa_mod.orm = orm_mod
        sys.modules["sqlalchemy.orm"] = orm_mod
    sa_orm = sys.modules.get("sqlalchemy.orm") or ModuleType("sqlalchemy.orm")
    if not hasattr(sa_orm, "Session"):
        sa_orm.Session = MagicMock()
    sys.modules["sqlalchemy.orm"] = sa_orm

    sa_attr = sys.modules.get("sqlalchemy.orm.attributes") or ModuleType("sqlalchemy.orm.attributes")
    if not hasattr(sa_attr, "flag_modified"):
        sa_attr.flag_modified = MagicMock()
    sys.modules["sqlalchemy.orm.attributes"] = sa_attr


_stub_misc()
