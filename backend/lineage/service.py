"""Lineage graph assembly (Phase 6).

Builds an end-to-end DAG over Pipeline outputs, dbt model outputs, and
dashboard widgets for a given OwnerScope. Lineage is *derived*: nothing
stored to disk. Short-TTL Redis cache (see cache.py) makes repeat reads
cheap; the cache invalidates on `lineage:invalidate` pub/sub messages
emitted by the Pipeline runner, dbt runner, and resource-lifecycle
deletes (Phases 2 / 4).
"""
from __future__ import annotations

import gzip
import json
import logging
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from backend.data_plane.scope import OwnerScope
from backend.utils.sql_refs import extract_table_refs

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Graph types
# ---------------------------------------------------------------------------

NodeKind = str  # "connection" | "table" | "widget"
EdgeKind = str  # "source_to_table" | "table_to_table" | "table_to_widget"


@dataclass(frozen=True)
class Node:
    id: str
    kind: NodeKind
    name: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    kind: EdgeKind


@dataclass
class LineageGraph:
    scope_kind: str
    scope_id: str
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    incomplete_widgets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope_kind": self.scope_kind,
            "scope_id": self.scope_id,
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [asdict(e) for e in self.edges],
            "incomplete_widgets": list(self.incomplete_widgets),
        }


# ---------------------------------------------------------------------------
# Node ID conventions (stable across runs so cache hits work)
# ---------------------------------------------------------------------------

def connection_node_id(connection_id: int) -> str:
    return f"conn:{connection_id}"


def table_node_id(table_name: str) -> str:
    return f"table:{table_name.lower()}"


def widget_node_id(widget_id: str) -> str:
    return f"widget:{widget_id}"


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_graph(scope: OwnerScope, db: Session) -> LineageGraph:
    """Assemble the full lineage graph for *scope*.

    Pipeline outputs and dbt model outputs are first-class table nodes.
    Source connections feed pipeline-output tables. dbt models depend on
    upstream tables (parsed from `dbt_runs.manifest_blob`). Dashboard
    widgets depend on tables they read from (parsed via sqlglot).
    """
    from backend.models.pipeline import Pipeline
    from backend.models.transforms import DbtModel, DbtRun
    from backend.models.dashboard import Dashboard

    graph = LineageGraph(scope_kind=scope.kind, scope_id=scope.id)
    nodes: dict[str, Node] = {}
    edges: list[Edge] = []

    def add_node(n: Node) -> None:
        if n.id not in nodes:
            nodes[n.id] = n

    def add_edge(src: str, dst: str, kind: EdgeKind) -> None:
        if src in nodes and dst in nodes:
            edges.append(Edge(src=src, dst=dst, kind=kind))

    # 1. Pipeline → table edges (source connection feeds a DataPlane table)
    pipelines = (
        db.query(Pipeline)
        .filter(
            Pipeline.owner_scope_kind == scope.kind,
            Pipeline.owner_scope_id == scope.id,
        )
        .all()
    )
    for p in pipelines:
        c_id = connection_node_id(p.source_connection_id)
        t_id = table_node_id(p.target_table)
        add_node(Node(id=c_id, kind="connection", name=str(p.source_connection_id),
                      meta={"connection_id": p.source_connection_id}))
        add_node(Node(id=t_id, kind="table", name=p.target_table,
                      meta={
                          "writer": "pipeline",
                          "pipeline_id": p.id,
                          "pipeline_name": p.name,
                          "last_run_at": p.last_run_at.isoformat() if p.last_run_at else None,
                          "last_run_status": p.last_run_status,
                      }))
        add_edge(c_id, t_id, "source_to_table")

    # 2. dbt model → table edges (depends_on.nodes from latest manifest)
    models = (
        db.query(DbtModel)
        .filter(
            DbtModel.owner_scope_kind == scope.kind,
            DbtModel.owner_scope_id == scope.id,
        )
        .all()
    )
    for m in models:
        t_id = table_node_id(m.name)
        add_node(Node(id=t_id, kind="table", name=m.name,
                      meta={
                          "writer": "dbt",
                          "model_id": m.id,
                          "materialization": m.materialization,
                          "last_run_at": m.last_run_at.isoformat() if m.last_run_at else None,
                          "last_run_status": m.last_run_status,
                      }))

    # Decompress latest manifest for this scope
    latest_manifest = _latest_manifest(scope, db)
    if latest_manifest:
        for nname, ndata in (latest_manifest.get("nodes") or {}).items():
            # dbt manifest node names look like "model.proj.model_name"; the model name is the last segment
            if not isinstance(ndata, dict):
                continue
            if ndata.get("resource_type") != "model":
                continue
            model_name = ndata.get("name") or nname.split(".")[-1]
            depends_on = (ndata.get("depends_on") or {}).get("nodes") or []
            child = table_node_id(model_name)
            if child not in nodes:
                continue  # the model isn't in our scope
            for dep in depends_on:
                # Manifest dependency reference: "model.proj.foo" or "source.proj.schema.foo"
                parent_name = dep.split(".")[-1]
                parent_id = table_node_id(parent_name)
                # Only draw the edge if the parent is a table we know about
                if parent_id in nodes:
                    add_edge(parent_id, child, "table_to_table")

    # 3. Dashboard widget edges (table → widget)
    dashboards = _scope_dashboards(scope, db)
    incomplete: list[str] = []
    widget_status_updates: list[tuple[Dashboard, str, str]] = []
    for dash in dashboards:
        widgets = dash.widgets or []
        changed = False
        for w in widgets:
            if not isinstance(w, dict):
                continue
            wid = w.get("id") or str(uuid.uuid4())
            data_source = w.get("dataSource") or {}
            sql = data_source.get("sql") or ""
            w_node_id = widget_node_id(wid)
            add_node(Node(id=w_node_id, kind="widget", name=w.get("title") or wid,
                          meta={
                              "dashboard_id": dash.id,
                              "lineage_status": w.get("lineage_status", "unknown"),
                          }))
            if not sql:
                continue
            refs = extract_table_refs(sql)
            if refs:
                new_status = "parsed"
                for tbl in refs:
                    t_id = table_node_id(tbl)
                    if t_id not in nodes:
                        # Widget references a table outside the DataPlane (e.g., live source)
                        # Still add the table as a stub so the edge is visible.
                        add_node(Node(id=t_id, kind="table", name=tbl,
                                      meta={"writer": "external"}))
                    add_edge(t_id, w_node_id, "table_to_widget")
            else:
                # sqlglot couldn't parse — mark incomplete and queue admin review
                new_status = "incomplete"
                incomplete.append(wid)
                _enqueue_parse_failure(db, wid, data_source.get("connectionId"), sql)

            if w.get("lineage_status") != new_status:
                w["lineage_status"] = new_status
                changed = True

        if changed:
            # Re-stamp JSON column so SQLAlchemy detects the change
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(dash, "widgets")

    if incomplete:
        try:
            db.commit()
        except Exception:
            logger.warning("build_graph: failed to commit widget lineage_status updates", exc_info=True)
            db.rollback()
    else:
        # Still commit any clean status flips
        try:
            db.commit()
        except Exception:
            db.rollback()

    graph.nodes = list(nodes.values())
    graph.edges = edges
    graph.incomplete_widgets = incomplete
    return graph


# ---------------------------------------------------------------------------
# BFS traversal
# ---------------------------------------------------------------------------

def upstream(graph: LineageGraph, node_id: str, hops: int = 2) -> list[Node]:
    return _bfs(graph, node_id, hops, direction="upstream")


def downstream(graph: LineageGraph, node_id: str, hops: int = 2) -> list[Node]:
    return _bfs(graph, node_id, hops, direction="downstream")


def _bfs(graph: LineageGraph, start: str, hops: int, direction: str) -> list[Node]:
    by_id = {n.id: n for n in graph.nodes}
    if start not in by_id:
        return []

    adj_in: dict[str, list[str]] = defaultdict(list)
    adj_out: dict[str, list[str]] = defaultdict(list)
    for e in graph.edges:
        adj_out[e.src].append(e.dst)
        adj_in[e.dst].append(e.src)

    queue: deque[tuple[str, int]] = deque([(start, 0)])
    visited: set[str] = {start}
    out: list[Node] = []
    adj = adj_in if direction == "upstream" else adj_out
    while queue:
        cur, depth = queue.popleft()
        if depth >= hops:
            continue
        for nb in adj[cur]:
            if nb in visited:
                continue
            visited.add(nb)
            out.append(by_id[nb])
            queue.append((nb, depth + 1))
    return out


# ---------------------------------------------------------------------------
# last_write
# ---------------------------------------------------------------------------

def last_write(table_name: str, scope: OwnerScope, db: Session) -> Optional[dict]:
    """Return metadata for the most recent write to *table_name* in *scope*.

    Looks up the latest pipeline_runs row (if a Pipeline targets this table)
    and the latest dbt_runs row (if a dbt model produced this table). Returns
    whichever finished most recently.
    """
    from backend.models.pipeline import Pipeline, PipelineRun
    from backend.models.transforms import DbtModel, DbtRun

    candidates: list[dict] = []

    pipeline = (
        db.query(Pipeline)
        .filter(
            Pipeline.owner_scope_kind == scope.kind,
            Pipeline.owner_scope_id == scope.id,
            Pipeline.target_table == table_name,
        )
        .first()
    )
    if pipeline:
        run = (
            db.query(PipelineRun)
            .filter(PipelineRun.pipeline_id == pipeline.id)
            .order_by(PipelineRun.started_at.desc())
            .first()
        )
        if run:
            candidates.append({
                "writer": "pipeline",
                "run_id": run.id,
                "pipeline_id": pipeline.id,
                "started_at": _iso(run.started_at),
                "finished_at": _iso(run.finished_at),
                "status": run.status,
                "rows_written": run.rows_written,
            })

    model = (
        db.query(DbtModel)
        .filter(
            DbtModel.owner_scope_kind == scope.kind,
            DbtModel.owner_scope_id == scope.id,
            DbtModel.name == table_name,
        )
        .first()
    )
    if model:
        run = (
            db.query(DbtRun)
            .filter(
                DbtRun.owner_scope_kind == scope.kind,
                DbtRun.owner_scope_id == scope.id,
            )
            .order_by(DbtRun.started_at.desc())
            .first()
        )
        if run:
            candidates.append({
                "writer": "dbt",
                "run_id": run.id,
                "model_id": model.id,
                "started_at": _iso(run.started_at),
                "finished_at": _iso(run.finished_at),
                "status": run.status,
            })

    if not candidates:
        return None
    candidates.sort(key=lambda c: c.get("finished_at") or c.get("started_at") or "", reverse=True)
    return candidates[0]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _latest_manifest(scope: OwnerScope, db: Session) -> Optional[dict]:
    from backend.models.transforms import DbtRun
    run = (
        db.query(DbtRun)
        .filter(
            DbtRun.owner_scope_kind == scope.kind,
            DbtRun.owner_scope_id == scope.id,
            DbtRun.manifest_blob.isnot(None),
        )
        .order_by(DbtRun.started_at.desc())
        .first()
    )
    if not run or not run.manifest_blob:
        return None
    try:
        return json.loads(gzip.decompress(run.manifest_blob).decode("utf-8"))
    except Exception:
        logger.warning("Failed to decode dbt manifest_blob for run %s", run.id, exc_info=True)
        return None


def _scope_dashboards(scope: OwnerScope, db: Session) -> Iterable:
    from backend.models.dashboard import Dashboard
    # Dashboards are user-owned today; org/team scopes return any dashboard
    # owned by a member of that scope. v1 keeps it simple: filter user scope only,
    # other scopes return the full set.
    q = db.query(Dashboard)
    if scope.kind == "user":
        q = q.filter(Dashboard.user_id == scope.id)
    return q.all()


def _enqueue_parse_failure(db: Session, widget_id: str, connection_id: Optional[int], sql: str) -> None:
    """Add the widget to widgets_pending_manual_rewrite (idempotent)."""
    from backend.migration.substrate import WidgetPendingManualRewrite
    if connection_id is None:
        return
    existing = (
        db.query(WidgetPendingManualRewrite)
        .filter(
            WidgetPendingManualRewrite.widget_id == widget_id,
            WidgetPendingManualRewrite.status == "pending",
        )
        .first()
    )
    if existing:
        # ensure source is set correctly
        if getattr(existing, "source", None) != "parse_failure":
            existing.source = "parse_failure"
        return
    row = WidgetPendingManualRewrite(
        id=str(uuid.uuid4()),
        widget_id=widget_id,
        connection_id=connection_id,
        current_sql=sql,
        status="pending",
        source="parse_failure",
    )
    db.add(row)
