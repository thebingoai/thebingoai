"""Resolve and instantiate a DataPlane for a given owner scope.

This service is the single place that knows how to load a DataPlaneModel row,
decrypt its credentials, and hand back a concrete DataPlane instance.
"""
from __future__ import annotations

import logging
from typing import Optional

from backend.data_plane.scope import OwnerScope

logger = logging.getLogger(__name__)


def get_default_plane(scope: OwnerScope, db=None):
    """Return the default DataPlane for *scope*, walking the scope chain.

    Resolution order: starts at *scope*, then walks to its parent (user→org,
    team→org). First ``is_default`` row at any scope wins. Falls back to a
    ``LocalFilesystemDataPlane`` if no row is found at any level.
    """
    from sqlalchemy import tuple_
    from backend.models.data_plane import DataPlaneModel

    if db is None:
        from backend.database.session import SessionLocal
        with SessionLocal() as _db:
            return get_default_plane(scope, _db)

    chain = _scope_chain(scope, db)
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
            return _instantiate(row)
    return _default_fallback()


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


def _default_fallback():
    """Return the per-scope plane when no `data_planes` row matches.

    In dev (`DISABLE_LOCAL_DATA_PLANE=false`) this is LocalFilesystemDataPlane.
    In prod with the lockdown on, this is the Bingo-managed internal GCP plane.
    """
    from backend.config import settings
    if getattr(settings, "disable_local_data_plane", False):
        return _internal_gcp_plane()
    from backend.data_plane.local_filesystem import LocalFilesystemDataPlane
    root = getattr(settings, "data_plane_local_root", "/data/data_plane")
    return LocalFilesystemDataPlane(root_path=root)


def _instantiate(row):
    from backend.security.encryption import decrypt_password

    if row.type == "local_filesystem":
        from backend.data_plane.local_filesystem import LocalFilesystemDataPlane
        root = row.config.get("root_path", "/data/data_plane")
        return LocalFilesystemDataPlane(root_path=root)

    if row.type == "google_cloud_project":
        from backend.data_plane.bigquery_gcs import BigQueryGCSPlane
        sa_json = decrypt_password(row.credentials_encrypted) if row.credentials_encrypted else ""
        return BigQueryGCSPlane(
            gcp_project=row.config["gcp_project"],
            gcs_bucket=row.config["gcs_bucket"],
            bq_dataset=row.config["bq_dataset"],
            service_account_json=sa_json,
        )

    raise ValueError(f"Unknown data_plane type: {row.type!r}")


def _read_internal_sa(path: str) -> str:
    """Read the internal-GCP service-account JSON from disk.

    Path-based read keeps the SA off env (env vars leak to subprocess logs);
    secret is mounted as a file by infra.
    """
    with open(path) as f:
        return f.read()


def _internal_gcp_plane():
    """Construct the Bingo-managed internal BigQueryGCSPlane from env."""
    from backend.config import settings
    from backend.data_plane.bigquery_gcs import BigQueryGCSPlane

    sa_json = _read_internal_sa(settings.internal_gcp_sa_json_path)
    return BigQueryGCSPlane(
        gcp_project=settings.internal_gcp_project,
        gcs_bucket=settings.internal_gcs_bucket,
        bq_dataset=settings.internal_bq_dataset,
        service_account_json=sa_json,
    )
