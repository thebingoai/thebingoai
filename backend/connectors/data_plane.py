"""DataPlaneConnector — exposes an Org's DataPlane as a queryable connection."""
from __future__ import annotations

import logging
from typing import Any, Optional

from backend.connectors.base import QueryResult, TableSchema
from backend.data_plane.scope import OwnerScope

logger = logging.getLogger(__name__)


class DataPlaneConnector:
    """Wraps a DataPlane instance so it fits the connector interface."""

    def __init__(self, plane, scope: OwnerScope) -> None:
        self._plane = plane
        self._scope = scope

    @classmethod
    def from_connection(cls, connection) -> "DataPlaneConnector":
        from backend.services.data_plane_service import get_plane_for_connection
        plane, scope = get_plane_for_connection(connection)
        return cls(plane, scope)

    def test_connection(self) -> bool:
        try:
            self._plane.list_tables(self._scope)
            return True
        except Exception as exc:
            raise ConnectionError(f"DataPlane not reachable: {exc}") from exc

    def get_tables(self, schema: Optional[str] = None) -> list[str]:
        return self._plane.list_tables(self._scope)

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
