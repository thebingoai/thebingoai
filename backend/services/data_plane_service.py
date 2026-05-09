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
    """Return the default DataPlane for *scope*, or a LocalFilesystemDataPlane if none configured."""
    from backend.models.data_plane import DataPlaneModel

    if db is None:
        from backend.database.session import SessionLocal
        with SessionLocal() as _db:
            return get_default_plane(scope, _db)

    row = (
        db.query(DataPlaneModel)
        .filter(
            DataPlaneModel.owner_scope_kind == scope.kind,
            DataPlaneModel.owner_scope_id == scope.id,
            DataPlaneModel.is_default == True,
        )
        .first()
    )

    if row is None:
        return _local_fallback()

    return _instantiate(row)


def get_plane_for_connection(connection):
    """Derive scope from *connection* and return (plane, scope)."""
    scope = OwnerScope.from_connection(connection)
    plane = get_default_plane(scope)
    return plane, scope


def _local_fallback():
    from backend.config import settings
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
