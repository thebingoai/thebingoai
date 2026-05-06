"""Lineage service unit tests — graph assembly, BFS traversal, last_write."""
from __future__ import annotations

import gzip
import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers — build a fake DB session that returns canned rows for each model
# ---------------------------------------------------------------------------

class _FakeQuery:
    def __init__(self, rows):
        self._rows = list(rows)
    def filter(self, *_a, **_kw): return self
    def order_by(self, *_a, **_kw): return self
    def first(self): return self._rows[0] if self._rows else None
    def all(self): return list(self._rows)


def _make_db(*, pipelines=(), models=(), dbt_runs=(), dashboards=(), pipeline_runs=()):
    from backend.models.pipeline import Pipeline, PipelineRun
    from backend.models.transforms import DbtModel, DbtRun
    from backend.models.dashboard import Dashboard

    table_to_rows = {
        Pipeline: pipelines,
        PipelineRun: pipeline_runs,
        DbtModel: models,
        DbtRun: dbt_runs,
        Dashboard: dashboards,
    }

    db = MagicMock()
    def query(model):
        return _FakeQuery(table_to_rows.get(model, ()))
    db.query.side_effect = query
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.add = MagicMock()
    return db


def _pipeline(*, id="p1", target="t_orders", source_conn=10, owner="u1"):
    from backend.models.pipeline import Pipeline
    p = Pipeline()
    p.id = id
    p.owner_scope_kind = "user"
    p.owner_scope_id = owner
    p.source_connection_id = source_conn
    p.target_table = target
    p.name = id
    p.last_run_at = datetime(2026, 5, 6, 12, 0, 0)
    p.last_run_status = "success"
    return p


def _dbt_model(*, id="m1", name="orders_summary", owner="u1"):
    from backend.models.transforms import DbtModel
    m = DbtModel()
    m.id = id
    m.owner_scope_kind = "user"
    m.owner_scope_id = owner
    m.name = name
    m.materialization = "table"
    m.last_run_at = None
    m.last_run_status = None
    return m


def _dbt_run(manifest, owner="u1"):
    from backend.models.transforms import DbtRun
    r = DbtRun()
    r.id = "run-1"
    r.owner_scope_kind = "user"
    r.owner_scope_id = owner
    r.started_at = datetime(2026, 5, 6, 11, 0, 0)
    r.finished_at = datetime(2026, 5, 6, 11, 30, 0)
    r.status = "success"
    r.manifest_blob = gzip.compress(json.dumps(manifest).encode())
    return r


def _dashboard(*, id=1, user_id="u1", widgets=()):
    from backend.models.dashboard import Dashboard
    d = Dashboard()
    d.id = id
    d.user_id = user_id
    d.widgets = list(widgets)
    return d


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_build_graph_simple_chain():
    """source connection → pipeline output → dbt model → widget."""
    from backend.data_plane.scope import OwnerScope
    from backend.lineage import service

    manifest = {
        "nodes": {
            "model.proj.orders_summary": {
                "resource_type": "model",
                "name": "orders_summary",
                "depends_on": {"nodes": ["source.proj.raw.t_orders"]},
            }
        }
    }
    widget = {
        "id": "w1",
        "title": "Top customers",
        "dataSource": {
            "connectionId": 10,
            "sql": "SELECT * FROM orders_summary LIMIT 10",
        },
    }
    db = _make_db(
        pipelines=[_pipeline(target="t_orders", source_conn=10)],
        models=[_dbt_model(name="orders_summary")],
        dbt_runs=[_dbt_run(manifest)],
        dashboards=[_dashboard(widgets=[widget])],
    )

    g = service.build_graph(OwnerScope("user", "u1"), db)

    node_ids = {n.id for n in g.nodes}
    assert service.connection_node_id(10) in node_ids
    assert service.table_node_id("t_orders") in node_ids
    assert service.table_node_id("orders_summary") in node_ids
    assert service.widget_node_id("w1") in node_ids

    edges = [(e.src, e.dst, e.kind) for e in g.edges]
    assert (service.connection_node_id(10), service.table_node_id("t_orders"), "source_to_table") in edges
    assert (service.table_node_id("t_orders"), service.table_node_id("orders_summary"), "table_to_table") in edges
    assert (service.table_node_id("orders_summary"), service.widget_node_id("w1"), "table_to_widget") in edges


def test_build_graph_unparseable_widget_is_incomplete():
    """A widget with non-parseable SQL gets lineage_status='incomplete'."""
    from backend.data_plane.scope import OwnerScope
    from backend.lineage import service

    widget = {
        "id": "w_bad",
        "dataSource": {"connectionId": 10, "sql": "this is ::: not !!! valid sql {{}}"},
    }
    dash = _dashboard(widgets=[widget])
    db = _make_db(dashboards=[dash])

    g = service.build_graph(OwnerScope("user", "u1"), db)

    assert "w_bad" in g.incomplete_widgets
    assert dash.widgets[0]["lineage_status"] == "incomplete"


def test_build_graph_parseable_widget_marked_parsed():
    from backend.data_plane.scope import OwnerScope
    from backend.lineage import service

    widget = {
        "id": "w_ok",
        "dataSource": {"connectionId": 10, "sql": "SELECT * FROM orders"},
    }
    dash = _dashboard(widgets=[widget])
    db = _make_db(dashboards=[dash])

    g = service.build_graph(OwnerScope("user", "u1"), db)

    assert "w_ok" not in g.incomplete_widgets
    assert dash.widgets[0]["lineage_status"] == "parsed"


def test_bfs_upstream_and_downstream_respect_hops():
    from backend.lineage import service

    g = service.LineageGraph(scope_kind="user", scope_id="u1")
    g.nodes = [
        service.Node(id="a", kind="connection", name="a"),
        service.Node(id="b", kind="table", name="b"),
        service.Node(id="c", kind="table", name="c"),
        service.Node(id="d", kind="widget", name="d"),
    ]
    g.edges = [
        service.Edge(src="a", dst="b", kind="source_to_table"),
        service.Edge(src="b", dst="c", kind="table_to_table"),
        service.Edge(src="c", dst="d", kind="table_to_widget"),
    ]

    up_1 = {n.id for n in service.upstream(g, "d", hops=1)}
    up_2 = {n.id for n in service.upstream(g, "d", hops=2)}
    up_3 = {n.id for n in service.upstream(g, "d", hops=3)}
    assert up_1 == {"c"}
    assert up_2 == {"c", "b"}
    assert up_3 == {"c", "b", "a"}

    dn_2 = {n.id for n in service.downstream(g, "a", hops=2)}
    assert dn_2 == {"b", "c"}


def test_last_write_prefers_most_recent_finish():
    from backend.data_plane.scope import OwnerScope
    from backend.lineage import service
    from backend.models.pipeline import Pipeline, PipelineRun
    from backend.models.transforms import DbtModel, DbtRun

    pipeline = _pipeline(target="t_orders")
    pipeline_run = PipelineRun()
    pipeline_run.id = "pr-1"
    pipeline_run.pipeline_id = pipeline.id
    pipeline_run.started_at = datetime(2026, 5, 6, 10, 0)
    pipeline_run.finished_at = datetime(2026, 5, 6, 10, 5)
    pipeline_run.status = "success"
    pipeline_run.rows_written = 100

    dbt_model = _dbt_model(name="t_orders")
    dbt_run = _dbt_run({"nodes": {}})

    db = _make_db(
        pipelines=[pipeline], pipeline_runs=[pipeline_run],
        models=[dbt_model], dbt_runs=[dbt_run],
    )
    out = service.last_write("t_orders", OwnerScope("user", "u1"), db)
    # dbt_run.finished_at is 11:30, pipeline_run.finished_at is 10:05 → dbt wins
    assert out is not None
    assert out["writer"] == "dbt"


def test_last_write_returns_none_for_unknown_table():
    from backend.data_plane.scope import OwnerScope
    from backend.lineage import service

    db = _make_db()
    assert service.last_write("nonexistent", OwnerScope("user", "u1"), db) is None
