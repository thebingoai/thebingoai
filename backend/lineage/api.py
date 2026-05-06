"""Lineage API router (Phase 6)."""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.database.session import get_db
from backend.data_plane.scope import OwnerScope
from backend.lineage import cache, service
from backend.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lineage", tags=["lineage"])


def _resolve_scope(
    scope_kind: Optional[str],
    scope_id: Optional[str],
    current_user: User,
) -> OwnerScope:
    """Default to the current user's scope; otherwise return the requested scope.

    Phase G governance gates non-user scopes; before G lands, allow self + any
    org/team the user is a member of (best-effort: trust the caller).
    """
    if not scope_kind or not scope_id:
        return OwnerScope("user", str(current_user.id))
    if scope_kind == "user" and str(scope_id) != str(current_user.id):
        # Without governance, only allow viewing your own user scope
        raise HTTPException(status_code=403, detail="Cannot view another user's lineage scope")
    return OwnerScope(scope_kind, str(scope_id))


def _get_or_build(scope: OwnerScope, db: Session) -> dict:
    cached = cache.get_cached(scope.kind, scope.id)
    if cached:
        return cached
    graph = service.build_graph(scope, db)
    payload = graph.to_dict()
    cache.set_cached(scope.kind, scope.id, payload)
    return payload


@router.get("/graph")
def get_graph(
    scope_kind: Optional[str] = Query(default=None),
    scope_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full lineage graph for a scope (defaults to the caller's user scope)."""
    scope = _resolve_scope(scope_kind, scope_id, current_user)
    return _get_or_build(scope, db)


@router.get("/dashboard/{dashboard_id}")
def get_dashboard_lineage(
    dashboard_id: int,
    hops: int = Query(default=3, ge=1, le=10),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return upstream lineage for every widget in a dashboard."""
    from backend.models.dashboard import Dashboard
    dash = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dash:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    if str(dash.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your dashboard")

    scope = OwnerScope("user", str(current_user.id))
    graph_dict = _get_or_build(scope, db)
    graph = _hydrate(graph_dict)

    out: dict[str, Any] = {"dashboard_id": dashboard_id, "widgets": []}
    for w in (dash.widgets or []):
        if not isinstance(w, dict):
            continue
        wid = w.get("id")
        if not wid:
            continue
        node_id = service.widget_node_id(wid)
        upstream_nodes = service.upstream(graph, node_id, hops=hops)
        out["widgets"].append({
            "widget_id": wid,
            "title": w.get("title"),
            "lineage_status": w.get("lineage_status", "unknown"),
            "upstream": [n.__dict__ for n in upstream_nodes],
        })
    return out


@router.get("/connection/{connection_id}")
def get_connection_lineage(
    connection_id: int,
    hops: int = Query(default=3, ge=1, le=10),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return downstream lineage from a source connection (tables + dashboards it feeds)."""
    from backend.models.database_connection import DatabaseConnection
    conn = db.query(DatabaseConnection).filter(DatabaseConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    if str(conn.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your connection")

    scope = OwnerScope("user", str(current_user.id))
    graph_dict = _get_or_build(scope, db)
    graph = _hydrate(graph_dict)

    node_id = service.connection_node_id(connection_id)
    downstream_nodes = service.downstream(graph, node_id, hops=hops)
    return {
        "connection_id": connection_id,
        "downstream": [n.__dict__ for n in downstream_nodes],
    }


@router.get("/table/{table_name}")
def get_table_lineage(
    table_name: str,
    hops: int = Query(default=2, ge=1, le=10),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upstream + downstream + last_write for a DataPlane table."""
    scope = OwnerScope("user", str(current_user.id))
    graph_dict = _get_or_build(scope, db)
    graph = _hydrate(graph_dict)

    node_id = service.table_node_id(table_name)
    return {
        "table": table_name,
        "upstream": [n.__dict__ for n in service.upstream(graph, node_id, hops=hops)],
        "downstream": [n.__dict__ for n in service.downstream(graph, node_id, hops=hops)],
        "last_write": service.last_write(table_name, scope, db),
    }


@router.post("/invalidate")
def invalidate_scope(
    scope_kind: Optional[str] = None,
    scope_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Manual cache invalidation (used by dashboard widget edits)."""
    scope = _resolve_scope(scope_kind, scope_id, current_user)
    cache.publish_invalidation(scope.kind, scope.id, source="manual")
    cache.invalidate(scope.kind, scope.id)
    return {"invalidated": True, "scope_kind": scope.kind, "scope_id": scope.id}


def _hydrate(graph_dict: dict) -> service.LineageGraph:
    """Reconstruct a LineageGraph from its serialized form (for traversal)."""
    g = service.LineageGraph(
        scope_kind=graph_dict.get("scope_kind", ""),
        scope_id=graph_dict.get("scope_id", ""),
    )
    g.nodes = [service.Node(**n) for n in graph_dict.get("nodes", [])]
    g.edges = [service.Edge(**e) for e in graph_dict.get("edges", [])]
    g.incomplete_widgets = list(graph_dict.get("incomplete_widgets", []))
    return g
