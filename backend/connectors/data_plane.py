"""DataPlaneConnector — exposes an Org's DataPlane as a queryable connection."""
from __future__ import annotations

import logging
from typing import Any, Optional

from backend.connectors.base import QueryResult, TableSchema
from backend.data_plane.scope import OwnerScope

logger = logging.getLogger(__name__)


class DataPlaneConnector:
    """Wraps a DataPlane instance so it fits the connector interface."""

    # Read path is the DataPlane (Parquet), not an origin database — widget
    # refresh reports `served_from="data_plane"` on this.
    serves_from_plane = True

    def __init__(self, plane, scope: OwnerScope, table_prefix: str | None = None) -> None:
        self._plane = plane
        self._scope = scope
        # An owner scope is shared by every connection that owner has, so the
        # plane's table list spans all of them. `table_prefix` narrows it to the
        # tables one connection owns; None means "every table in the scope"
        # (the plane-as-a-connection case, and pre-prefix migrations).
        self._table_prefix = table_prefix

    @classmethod
    def from_connection(cls, connection, table_prefix: str | None = None, db_session=None) -> "DataPlaneConnector":
        from backend.services.data_plane_service import get_plane_for_connection
        plane, scope = get_plane_for_connection(connection, db_session)
        return cls(plane, scope, table_prefix)

    def test_connection(self) -> bool:
        try:
            self._plane.list_tables(self._scope)
            return True
        except Exception as exc:
            raise ConnectionError(f"DataPlane not reachable: {exc}") from exc

    def get_schemas(self) -> list[str]:
        return ["main"]  # the plane is flat — one namespace

    def get_tables(self, schema: Optional[str] = None) -> list[str]:
        tables = self._plane.list_tables(self._scope)
        if self._table_prefix:
            tables = [t for t in tables if t.startswith(self._table_prefix)]
        return tables

    def get_foreign_keys(self, table_name: str, schema: Optional[str] = None) -> list[dict]:
        return []  # Parquet carries no FK metadata

    def get_table_schema(self, table_name: str, schema: Optional[str] = None) -> TableSchema:
        arrow_schema = self._plane.get_schema(self._scope, table_name)
        columns = [
            {"name": f.name, "type": str(f.type), "nullable": f.nullable, "primary_key": False}
            for f in arrow_schema
        ]
        return TableSchema(table_name=table_name, columns=columns)

    def execute_query(self, query: str, params: Optional[dict] = None) -> QueryResult:
        return self._plane.query(self._scope, query, params)

    def close(self) -> None:
        pass  # plane lifecycle managed by the task/service that owns it

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
