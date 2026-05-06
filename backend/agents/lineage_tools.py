"""Phase 6 lineage tools — exposed to orchestrator + dashboard agents.

Tools:
- get_lineage_upstream(table, hops=2): tables / connections that feed *table*
- get_lineage_downstream(table, hops=2): models / widgets fed by *table*
- get_last_write(table): writer + run id + timestamps + status for *table*
"""
from __future__ import annotations

import json
from typing import List

from backend.agents.context import AgentContext


def build_lineage_tools(context: AgentContext) -> List:
    from langchain_core.tools import tool

    @tool
    async def get_lineage_upstream(table: str, hops: int = 2) -> str:
        """Return upstream nodes (tables, source connections) for a DataPlane table.

        Args:
            table: DataPlane table name to inspect.
            hops: How many edges to traverse upstream (default 2, max 10).
        """
        return json.dumps(_neighborhood(context, table, hops, direction="upstream"))

    @tool
    async def get_lineage_downstream(table: str, hops: int = 2) -> str:
        """Return downstream nodes (other tables, dashboard widgets) for a DataPlane table.

        Args:
            table: DataPlane table name to inspect.
            hops: How many edges to traverse downstream (default 2, max 10).
        """
        return json.dumps(_neighborhood(context, table, hops, direction="downstream"))

    @tool
    async def get_last_write(table: str) -> str:
        """Return who wrote a DataPlane table last and when.

        Args:
            table: DataPlane table name to inspect.

        Returns:
            JSON with writer ('pipeline'|'dbt'), run_id, finished_at, status.
        """
        from backend.data_plane.scope import OwnerScope
        from backend.database.session import SessionLocal
        from backend.lineage import service

        scope = OwnerScope("user", str(context.user_id))
        with SessionLocal() as db:
            return json.dumps(service.last_write(table, scope, db) or {})

    return [get_lineage_upstream, get_lineage_downstream, get_last_write]


def _neighborhood(context: AgentContext, table: str, hops: int, direction: str) -> dict:
    from backend.data_plane.scope import OwnerScope
    from backend.database.session import SessionLocal
    from backend.lineage import service, cache

    hops = max(1, min(int(hops or 2), 10))
    scope = OwnerScope("user", str(context.user_id))
    cached = cache.get_cached(scope.kind, scope.id)
    with SessionLocal() as db:
        if cached:
            from backend.lineage.api import _hydrate
            graph = _hydrate(cached)
        else:
            graph = service.build_graph(scope, db)
            cache.set_cached(scope.kind, scope.id, graph.to_dict())

    node_id = service.table_node_id(table)
    fn = service.upstream if direction == "upstream" else service.downstream
    nodes = fn(graph, node_id, hops=hops)
    return {
        "table": table,
        "direction": direction,
        "hops": hops,
        "nodes": [n.__dict__ for n in nodes],
    }
