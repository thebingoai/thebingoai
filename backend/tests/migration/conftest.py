"""Local conftest for migration tests.

The root conftest stubs sqlalchemy.orm without DeclarativeBase, which breaks
substrate.py's top-level import chain (substrate → database.base → DeclarativeBase).

Strategy: stub the entire backend.database.base / backend.database chain at the
sys.modules level BEFORE pytest imports the test module, then add the missing
sqlalchemy symbols needed downstream.
"""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock


# ── 1. Fix sqlalchemy.orm missing DeclarativeBase ──────────────────────────

orm_mod = sys.modules.get("sqlalchemy.orm")
if orm_mod is not None and not hasattr(orm_mod, "DeclarativeBase"):
    # Provide a real-enough base so subclasses work
    class _DeclarativeBase:
        """Stand-in for SQLAlchemy DeclarativeBase.
        Accepts keyword arguments so ORM-style constructors work.
        """
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    orm_mod.DeclarativeBase = _DeclarativeBase

# ── 2. Fix sqlalchemy.dialects.postgresql missing JSONB ────────────────────

pg_mod = sys.modules.get("sqlalchemy.dialects.postgresql")
if pg_mod is not None and not hasattr(pg_mod, "JSONB"):
    pg_mod.JSONB = MagicMock()

# ── 3. Ensure sqlalchemy.sql.func exists ───────────────────────────────────

def _ensure_submod(parent_name: str, attr: str) -> ModuleType:
    full = f"{parent_name}.{attr}"
    if full not in sys.modules:
        mod = ModuleType(full)
        sys.modules[full] = mod
        parent = sys.modules.get(parent_name)
        if parent is not None:
            setattr(parent, attr, mod)
        return mod
    return sys.modules[full]


sql_mod = _ensure_submod("sqlalchemy", "sql")
if not hasattr(sql_mod, "func"):
    sql_mod.func = MagicMock()

# sqlalchemy.Index
sa_mod = sys.modules.get("sqlalchemy")
if sa_mod is not None and not hasattr(sa_mod, "Index"):
    sa_mod.Index = MagicMock()

# ── 4. Stub backend.database.base so the import chain resolves ─────────────

def _stub_backend_database():
    """
    Inject stub modules for backend.database.base and backend.database so that
    substrate.py's `from backend.database.base import Base, TimestampMixin`
    resolves without needing a real SQLAlchemy engine / database.
    """
    # Stub Base / TimestampMixin
    class _Base:
        """Minimal stand-in for SQLAlchemy DeclarativeBase.
        Accepts keyword arguments so ORM-style model constructors work.
        """

    # Inject __init__ outside the class body to avoid annotation confusion
    def _base_init(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    _Base.__init__ = _base_init

    class _TimestampMixin:
        pass

    # backend.database.base
    db_base_mod = ModuleType("backend.database.base")
    db_base_mod.Base = _Base
    db_base_mod.TimestampMixin = _TimestampMixin
    sys.modules.setdefault("backend.database.base", db_base_mod)

    # backend.database (re-export so `from backend.database.base import ...` still finds it)
    db_mod = ModuleType("backend.database")
    db_mod.Base = _Base
    db_mod.TimestampMixin = _TimestampMixin
    db_mod.engine = MagicMock()
    db_mod.SessionLocal = MagicMock()
    db_mod.get_db = MagicMock()
    sys.modules.setdefault("backend.database", db_mod)

    # backend.database.session (imported by substrate when db=None path)
    db_session_mod = ModuleType("backend.database.session")
    db_session_mod.SessionLocal = MagicMock()
    db_session_mod.engine = MagicMock()
    db_session_mod.get_db = MagicMock()
    sys.modules.setdefault("backend.database.session", db_session_mod)


_stub_backend_database()


# ── 5. Stub backend.security.encryption (needed by DatabaseConnection) ─────

def _stub_encryption():
    enc_mod = ModuleType("backend.security")
    sys.modules.setdefault("backend.security", enc_mod)

    enc_sub = ModuleType("backend.security.encryption")
    enc_sub.encrypt_password = lambda s: f"enc:{s}"
    enc_sub.decrypt_password = lambda s: s.replace("enc:", "") if s else s
    sys.modules.setdefault("backend.security.encryption", enc_sub)
    setattr(enc_mod, "encryption", enc_sub)


_stub_encryption()


# ── 6. Stub backend.data_plane.scope (OwnerScope.from_connection) ──────────

def _stub_data_plane():
    dp_mod = sys.modules.get("backend.data_plane")
    if dp_mod is None:
        dp_mod = ModuleType("backend.data_plane")
        sys.modules["backend.data_plane"] = dp_mod

    # scope sub-module
    scope_mod = ModuleType("backend.data_plane.scope")

    class _OwnerScope:
        def __init__(self, kind: str, id: str):
            self.kind = kind
            self.id = str(id)

        def as_path(self) -> str:
            return f"{self.kind}/{self.id}"

        @classmethod
        def from_connection(cls, conn) -> "_OwnerScope":
            if getattr(conn, "owner_scope_kind", None) and getattr(conn, "owner_scope_id", None):
                return cls(conn.owner_scope_kind, conn.owner_scope_id)
            if getattr(conn, "org_id", None):
                return cls("org", conn.org_id)
            return cls("user", conn.user_id)

    scope_mod.OwnerScope = _OwnerScope
    sys.modules.setdefault("backend.data_plane.scope", scope_mod)
    setattr(dp_mod, "scope", scope_mod)

    # protocol sub-module (DataPlane ABC)
    proto_mod = ModuleType("backend.data_plane.protocol")
    proto_mod.DataPlane = MagicMock()
    proto_mod.QueryResult = MagicMock()
    proto_mod.TableSchema = MagicMock()
    sys.modules.setdefault("backend.data_plane.protocol", proto_mod)

    # services.data_plane_service (get_default_plane)
    svc_mod = sys.modules.get("backend.services")
    if svc_mod is None:
        svc_mod = ModuleType("backend.services")
        sys.modules["backend.services"] = svc_mod

    dp_svc_mod = ModuleType("backend.services.data_plane_service")
    dp_svc_mod.get_default_plane = MagicMock()
    sys.modules.setdefault("backend.services.data_plane_service", dp_svc_mod)
    setattr(svc_mod, "data_plane_service", dp_svc_mod)


_stub_data_plane()


# ── 7. Stub backend.services.object_storage ────────────────────────────────

def _stub_object_storage():
    svc_mod = sys.modules.get("backend.services")
    if svc_mod is None:
        svc_mod = ModuleType("backend.services")
        sys.modules["backend.services"] = svc_mod

    os_mod = ModuleType("backend.services.object_storage")
    os_mod.download_bytes = MagicMock(return_value=None)
    os_mod.delete_object = MagicMock()
    sys.modules.setdefault("backend.services.object_storage", os_mod)
    setattr(svc_mod, "object_storage", os_mod)


_stub_object_storage()


# ── 8. Stub backend.models.* (DatabaseConnection, Dashboard) ───────────────

def _stub_models():
    """
    Stub backend.models.database_connection and backend.models.dashboard so the
    lazy imports inside migrate_connection / rollback_connection / widgets_referencing
    resolve without the real SQLAlchemy engine.
    """
    # --- backend.models.database_connection ---
    class _DatabaseConnection:
        __tablename__ = "database_connections"
        id: int = 1
        user_id: str = "user-1"
        org_id = None
        dataset_table_name = None
        source_filename = None
        owner_scope_kind: str = "user"
        owner_scope_id: str = "user-1"

    # Ensure the real class name is correct so model.__name__ fallback also works
    _DatabaseConnection.__name__ = "DatabaseConnection"

    class _DatabaseType:
        POSTGRES = "postgres"
        MYSQL = "mysql"

    dc_mod = ModuleType("backend.models.database_connection")
    dc_mod.DatabaseConnection = _DatabaseConnection
    dc_mod.DatabaseType = _DatabaseType
    sys.modules.setdefault("backend.models.database_connection", dc_mod)

    # --- backend.models.dashboard ---
    class _Dashboard:
        __tablename__ = "dashboards"
        id: int = 1
        user_id: str = "user-1"
        widgets = []

    _Dashboard.__name__ = "Dashboard"

    dash_mod = ModuleType("backend.models.dashboard")
    dash_mod.Dashboard = _Dashboard
    sys.modules.setdefault("backend.models.dashboard", dash_mod)

    # --- backend.models (package) ---
    models_mod = sys.modules.get("backend.models")
    if models_mod is None:
        models_mod = ModuleType("backend.models")
        sys.modules["backend.models"] = models_mod
    setattr(models_mod, "database_connection", dc_mod)
    setattr(models_mod, "dashboard", dash_mod)
    if not hasattr(models_mod, "DatabaseConnection"):
        models_mod.DatabaseConnection = _DatabaseConnection
    if not hasattr(models_mod, "Dashboard"):
        models_mod.Dashboard = _Dashboard


_stub_models()
