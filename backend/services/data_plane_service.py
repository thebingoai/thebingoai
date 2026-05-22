"""Resolve and instantiate a DataPlane for a given owner scope.

This service is the single place that knows how to load a DataPlaneModel row,
decrypt its credentials, and hand back a concrete DataPlane instance.

Shape A (per-Org auto-provisioned internal-GCP plane): there is no env-driven
singleton fallback. When `get_default_plane` finds no row in the scope chain
under lockdown, it invokes a plugin-registered provisioner (lazy "provision-on-miss")
before raising ``NoPlaneProvisionedError``. The bingo-admin plugin registers a
provisioner that creates a per-Org GCP plane synchronously. In dev (lockdown off),
the local-filesystem fallback is unchanged.
"""
from __future__ import annotations

import logging
from typing import Optional

from backend.data_plane.errors import (
    LocalPlaneUnderLockdownError,
    NoPlaneProvisionedError,
)
from backend.data_plane.scope import OwnerScope

logger = logging.getLogger(__name__)


_provision_on_miss = None

_registration_trace = []

def register_plane_provisioner(fn) -> None:
    """Plugin hook: register a function ``fn(org_id: str)`` that provisions a
    default plane for an Org. Called as a last-resort on a lockdown no-row miss
    before raising ``NoPlaneProvisionedError``. Scoped plugins (bingo-admin)
    register during ``on_startup``. Only one provisioner is active at a time."""
    global _provision_on_miss, _registration_trace
    import sys as _sys, traceback as _tb
    _provision_on_miss = fn
    _registration_trace.append(
        f"register_plane_provisioner called with {getattr(fn, '__name__', repr(fn))}"
        f" at {_tb.format_stack()[-1].strip()}"
    )
    logger.info("plane provisioner registered (%s)", getattr(fn, "__qualname__", repr(fn)))


def get_default_plane(scope: OwnerScope, db=None):
    """Return the default DataPlane for *scope*, walking the scope chain.

    Resolution order: starts at *scope*, then walks to its parent (user→org,
    team→org). First ``is_default`` row at any scope wins.

    No-row behaviour:
      - Under lockdown (`DISABLE_LOCAL_DATA_PLANE=true`): invoke the
        plugin-registered provisioner (lazy "provision-on-miss"), re-query,
        then raise ``NoPlaneProvisionedError`` if still missing.
      - Dev (lockdown off): return a ``LocalFilesystemDataPlane`` rooted at
        ``DATA_PLANE_LOCAL_ROOT`` — the historical dev-convenience path.
    """
    if db is None:
        from backend.database.session import SessionLocal
        with SessionLocal() as _db:
            return get_default_plane(scope, _db)

    row = _resolve_default_row(scope, db)
    if row is not None:
        return _instantiate(row)

    return _no_row_fallback(scope)


def _resolve_default_row(scope: OwnerScope, db):
    """Return the first ``is_default`` DataPlaneModel row in the scope chain, or None."""
    from sqlalchemy import tuple_
    from backend.models.data_plane import DataPlaneModel

    chain = _scope_chain(scope, db)
    row = _resolve_row(chain, db)
    if row is None and _try_provision_on_miss(chain):
        row = _resolve_row(chain, db)
    if row is not None:
        return _instantiate(row)

    return _no_row_fallback(scope)


def _resolve_row(chain, db):
    """Return the default DataPlaneModel row for the scope chain, or None."""
    from sqlalchemy import tuple_
    from backend.models.data_plane import DataPlaneModel

    rows = (
        db.query(DataPlaneModel)
        .filter(DataPlaneModel.is_default == True)
        .filter(
            tuple_(DataPlaneModel.owner_scope_kind, DataPlaneModel.owner_scope_id).in_(
                [(s.kind, s.id) for s in chain]
            )
        )
        .all()
    )
    by_key = {(r.owner_scope_kind, r.owner_scope_id): r for r in rows}
    for s in chain:
        row = by_key.get((s.kind, s.id))
        if row is not None:
            return row
    return None


def get_gcs_duckdb_reader(scope: OwnerScope, db=None):
    """Return a `GCSDuckDBReader` for DuckDB-over-GCS serving, or None (use BQ).

    None — caller falls back to the BQ path — when any of:
      - no default plane row, or it isn't a `google_cloud_project` plane;
      - the plane is **residency_locked** (data must not leave its region);
      - the plane is customer-managed (BYO) — internal HMAC only fits the
        bingo-managed internal bucket; per-plane HMAC is deferred;
      - internal GCS HMAC creds aren't configured.
    """
    if db is None:
        from backend.database.session import SessionLocal
        with SessionLocal() as _db:
            return get_gcs_duckdb_reader(scope, _db)

    from backend.config import settings

    row = _resolve_default_row(scope, db)
    if row is None or row.type != "google_cloud_project":
        return None
    if getattr(row, "residency_locked", False):
        return None
    if getattr(row, "managed_by", "customer") != "bingo":
        return None

    key_id = getattr(settings, "internal_gcs_hmac_key_id", None)
    secret = getattr(settings, "internal_gcs_hmac_secret", None)
    if not key_id or not secret:
        return None

    from backend.data_plane.gcs_duckdb import GCSDuckDBReader

    plane = _instantiate(row)
    return GCSDuckDBReader(plane.bucket, key_id, secret)


def _try_provision_on_miss(chain) -> bool:
    """Under lockdown, ask the registered provisioner to create a plane for the
    Org in *chain*. Returns True when an attempt was made (caller re-queries).

    Best-effort: exceptions are logged and swallowed — a miss after a failed
    attempt still raises ``NoPlaneProvisionedError`` for the caller to surface.
    """
    from backend.config import settings

    if not getattr(settings, "disable_local_data_plane", False):
        return False
    if _provision_on_miss is None:
        return False
    org_scope = next((s for s in chain if s.kind == "org"), None)
    if org_scope is None:
        return False
    logger.debug("attempting provision-on-miss for org=%s", org_scope.id)
    try:
        _provision_on_miss(org_scope.id)
    except Exception:
        logger.exception(
            "plane provision-on-miss failed for org %s", org_scope.id,
        )
    return True


def _no_row_fallback(scope: OwnerScope):
    """Resolve the no-row case based on lockdown state."""
    from backend.config import settings
    if getattr(settings, "disable_local_data_plane", False):
        raise NoPlaneProvisionedError(scope)
    from backend.data_plane.local_filesystem import LocalFilesystemDataPlane
    root = getattr(settings, "data_plane_local_root", "/data/data_plane")
    return LocalFilesystemDataPlane(root_path=root)


def _scope_chain(scope: OwnerScope, db) -> list[OwnerScope]:
    """Return *scope* followed by ancestor scopes (user→org, team→org)."""
    chain: list[OwnerScope] = [scope]
    if scope.kind == "user":
        from backend.models.user import User
        u = db.query(User).filter(User.id == scope.id).first()
        if u and u.org_id:
            chain.append(OwnerScope("org", u.org_id))
    elif scope.kind == "team":
        from backend.models.team import Team
        t = db.query(Team).filter(Team.id == scope.id).first()
        if t and t.org_id:
            chain.append(OwnerScope("org", t.org_id))
    return chain


def get_plane_for_connection(connection):
    """Derive scope from *connection* and return (plane, scope)."""
    scope = OwnerScope.from_connection(connection)
    plane = get_default_plane(scope)
    return plane, scope


def _instantiate(row):
    """Construct a DataPlane from a persisted row.

    Strict under lockdown: a `local_filesystem` row raises
    `LocalPlaneUnderLockdownError` rather than silently rerouting.
    """
    from backend.config import settings

    if row.type == "local_filesystem":
        if getattr(settings, "disable_local_data_plane", False):
            raise LocalPlaneUnderLockdownError(row.id)
        from backend.data_plane.local_filesystem import LocalFilesystemDataPlane
        root = row.config.get("root_path", "/data/data_plane")
        return LocalFilesystemDataPlane(root_path=root)

    if row.type == "google_cloud_project":
        from backend.security.encryption import decrypt_password
        from backend.data_plane.bigquery_gcs import BigQueryGCSPlane
        sa_json = (
            decrypt_password(row.credentials_encrypted)
            if row.credentials_encrypted else ""
        )
        return BigQueryGCSPlane(
            gcp_project=row.config["gcp_project"],
            gcs_bucket=row.config["gcs_bucket"],
            bq_dataset=row.config["bq_dataset"],
            service_account_json=sa_json,
        )

    raise ValueError(f"Unknown data_plane type: {row.type!r}")


def check_internal_gcp_config() -> None:
    """Boot-time precondition for DISABLE_LOCAL_DATA_PLANE.

    Validates the internal SA + project are configured. Per-Org bucket +
    dataset names are stored on each `data_planes` row (auto-provisioned
    on org create) — not env vars. Raises RuntimeError when the lockdown
    is on but the internal-GCP env is incomplete or the SA JSON file is
    unreadable. No-op when the lockdown is off.
    """
    import os
    from backend.config import settings

    if not getattr(settings, "disable_local_data_plane", False):
        return

    for field, env_name in (
        ("internal_gcp_project", "INTERNAL_GCP_PROJECT"),
        ("internal_gcp_sa_json_path", "INTERNAL_GCP_SA_JSON_PATH"),
    ):
        if not getattr(settings, field, None):
            raise RuntimeError(
                f"DISABLE_LOCAL_DATA_PLANE=true but {env_name} is empty"
            )

    sa_path = settings.internal_gcp_sa_json_path
    if not os.path.isfile(sa_path):
        raise RuntimeError(
            "DISABLE_LOCAL_DATA_PLANE=true but INTERNAL_GCP_SA_JSON_PATH "
            f"({sa_path!r}) is not a readable file"
        )
