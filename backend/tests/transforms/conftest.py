"""Local conftest for transforms tests.

The root conftest.py stubs sqlalchemy as a plain ModuleType (not a real
package), which means sqlalchemy.ext / sqlalchemy.dialects etc. can't be
imported via the normal backend.models.__init__ chain.

Strategy: stub backend.models.transforms and all heavy transitive imports
BEFORE test collection so the real SQLAlchemy package is never needed.
This mirrors the pattern in tests/migration/conftest.py.
"""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock


# ── 1. Stub backend.database.* ────────────────────────────────────────────

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

    db_mod = ModuleType("backend.database")
    db_mod.Base = _Base
    db_mod.TimestampMixin = _TimestampMixin
    db_mod.engine = MagicMock()
    db_mod.SessionLocal = MagicMock()
    db_mod.get_db = MagicMock()
    db_mod.base = db_base_mod
    sys.modules.setdefault("backend.database", db_mod)

    db_session_mod = ModuleType("backend.database.session")
    db_session_mod.SessionLocal = MagicMock()
    db_session_mod.engine = MagicMock()
    db_session_mod.get_db = MagicMock()
    sys.modules.setdefault("backend.database.session", db_session_mod)


_stub_backend_database()


# ── 2. Stub backend.models.transforms (DbtModel, DbtRun as plain classes) ─
# We bypass backend.models.__init__ entirely — it would cascade into
# sqlalchemy.ext which the root conftest doesn't stub.

def _stub_transforms_models():
    db_base_mod = sys.modules["backend.database.base"]
    _Base = db_base_mod.Base
    _TimestampMixin = db_base_mod.TimestampMixin

    class DbtModel(_Base, _TimestampMixin):
        __tablename__ = "dbt_models"
        id = None
        owner_scope_kind = None
        owner_scope_id = None
        name = None
        sql = None
        materialization = "table"
        unique_key = None
        cron = None
        next_run_at = None
        last_run_at = None
        last_run_status = None
        enabled = True
        created_by_user_id = None

    class DbtRun(_Base):
        __tablename__ = "dbt_runs"
        id = None
        owner_scope_kind = None
        owner_scope_id = None
        started_at = None
        finished_at = None
        status = "running"
        models_run = None
        manifest_blob = None
        triggered_by = None
        error_message = None

    transforms_mod = ModuleType("backend.models.transforms")
    transforms_mod.DbtModel = DbtModel
    transforms_mod.DbtRun = DbtRun
    sys.modules.setdefault("backend.models.transforms", transforms_mod)

    # Ensure backend.models package stub exists (without running its __init__)
    models_mod = sys.modules.get("backend.models")
    if models_mod is None:
        models_mod = ModuleType("backend.models")
        sys.modules["backend.models"] = models_mod
    if not isinstance(models_mod, ModuleType):
        # Already a real package — just inject the attribute
        pass
    else:
        models_mod.transforms = transforms_mod
        models_mod.DbtModel = DbtModel
        models_mod.DbtRun = DbtRun


_stub_transforms_models()


# ── 3. Stub dependencies required by transforms.api (top-level imports) ───

def _stub_api_deps():
    # backend.auth
    auth_mod = sys.modules.get("backend.auth")
    if auth_mod is None:
        auth_mod = ModuleType("backend.auth")
        sys.modules["backend.auth"] = auth_mod

    for submod, attrs in (
        ("backend.auth.dependencies", {"get_current_user": MagicMock()}),
        ("backend.auth.system_context", {
            "system_context": MagicMock(),
            "current_system_context": MagicMock(return_value=None),
        }),
    ):
        if submod not in sys.modules:
            m = ModuleType(submod)
            for k, v in attrs.items():
                setattr(m, k, v)
            sys.modules[submod] = m

    # backend.models.user (TransformCreate routes import User via auth.dependencies)
    if "backend.models.user" not in sys.modules:
        class _User:
            id: str = "user-1"
        user_mod = ModuleType("backend.models.user")
        user_mod.User = _User
        sys.modules["backend.models.user"] = user_mod

    # FastAPI: add attrs the root conftest may have missed
    fastapi_mod = sys.modules.get("fastapi")
    if fastapi_mod is not None:
        for attr in ("APIRouter", "Depends", "HTTPException", "status"):
            if not hasattr(fastapi_mod, attr):
                setattr(fastapi_mod, attr, MagicMock())


_stub_api_deps()
