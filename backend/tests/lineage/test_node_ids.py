"""Stable-id tests — these IDs are cache keys; renaming would invalidate caches."""
from __future__ import annotations


def test_connection_node_id_format():
    from backend.lineage import service
    assert service.connection_node_id(10) == "conn:10"


def test_table_node_id_lowercases():
    from backend.lineage import service
    assert service.table_node_id("Orders_Summary") == "table:orders_summary"
    assert service.table_node_id("ORDERS") == "table:orders"


def test_widget_node_id_format():
    from backend.lineage import service
    assert service.widget_node_id("w-1") == "widget:w-1"


def test_lineage_graph_to_dict_roundtrip():
    from backend.lineage import service

    g = service.LineageGraph(scope_kind="user", scope_id="u1")
    g.nodes = [service.Node(id="a", kind="connection", name="A")]
    g.edges = [service.Edge(src="a", dst="b", kind="source_to_table")]
    g.incomplete_widgets = ["w1"]

    payload = g.to_dict()
    assert payload["scope_kind"] == "user"
    assert payload["nodes"][0]["id"] == "a"
    assert payload["edges"][0]["src"] == "a"
    assert payload["incomplete_widgets"] == ["w1"]
