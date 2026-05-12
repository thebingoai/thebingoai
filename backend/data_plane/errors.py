"""Errors raised by the DataPlane resolver.

Distinct exception classes let route handlers (and Celery workers) return
targeted user-facing messages instead of a generic 500.
"""
from __future__ import annotations


class NoPlaneProvisionedError(RuntimeError):
    """Raised when get_default_plane finds no row for the scope chain.

    Caller should return a 503 with an admin-facing message; the front-end
    surfaces a banner pointing the admin at the Data Planes settings.
    """

    def __init__(self, scope):
        self.scope = scope
        super().__init__(
            f"No DataPlane provisioned for scope {scope.kind}:{scope.id}. "
            f"Admin must create one via DataPlanesView (or wait for "
            f"auto-provisioning to retry)."
        )


class LocalPlaneUnderLockdownError(RuntimeError):
    """Raised when a local_filesystem row is encountered under lockdown.

    Lockdown (`DISABLE_LOCAL_DATA_PLANE=true`) forbids the local Parquet
    backend in production. Pre-existing orphan local rows must be migrated
    to `google_cloud_project` or deleted.
    """

    def __init__(self, row_id):
        self.row_id = row_id
        super().__init__(
            f"DataPlane row {row_id} has type=local_filesystem but "
            f"DISABLE_LOCAL_DATA_PLANE=true. Migrate or delete the row."
        )
