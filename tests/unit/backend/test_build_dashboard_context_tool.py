"""Unit tests for _build_dashboard_context_tool in backend.agents.dashboard_agent.tools."""

import json

import pytest
from unittest.mock import MagicMock, patch

from backend.agents.dashboard_agent.tools import _build_dashboard_context_tool
from backend.agents.context import AgentContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(user_id="user-1", connections=None):
    ctx = AgentContext(user_id=user_id, available_connections=connections or [1])
    return ctx


def _make_connection(profiling_status="ready", name="Test DB"):
    conn = MagicMock()
    conn.id = 1
    conn.name = name
    conn.profiling_status = profiling_status
    conn.profiling_progress = None
    return conn


def _make_db_session_factory(connection=None):
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = connection
    factory = MagicMock(return_value=mock_session)
    return factory, mock_session


SAMPLE_CONN_CONTEXT = {
    "connectionId": 1,
    "tables": {
        "orders": {
            "schema": "public",
            "rowCount": 100,
            "columns": {
                "id": {"type": "integer", "role": "key"},
                "region": {"type": "varchar", "role": "dimension", "cardinality": 5},
                "amount": {"type": "numeric", "role": "measure"},
                "order_date": {"type": "date", "role": "dimension"},
                "customer_id": {"type": "integer", "role": "key"},
            },
        },
        "customers": {
            "schema": "public",
            "rowCount": 50,
            "columns": {
                "id": {"type": "integer", "role": "key"},
                "name": {"type": "varchar", "role": "attribute"},
                "segment": {"type": "varchar", "role": "dimension", "cardinality": 4},
            },
        },
    },
    "relationships": [
        {"from": "orders.customer_id", "to": "customers.id", "type": "many_to_one"},
    ],
}


# ---------------------------------------------------------------------------
# TestBuildDashboardContext
# ---------------------------------------------------------------------------

class TestBuildDashboardContext:
    """Tests for the build_dashboard_context tool produced by _build_dashboard_context_tool."""

    def test_happy_path_returns_sources_basejoin_dimensions(self):
        """Valid tables and dimensions produce success with sources, baseJoin, and dimensions."""
        context = _make_context()
        factory, session = _make_db_session_factory(_make_connection())
        tool_fn = _build_dashboard_context_tool(context, factory)

        with patch(
            "backend.services.connection_context.load_context_file",
            return_value=SAMPLE_CONN_CONTEXT,
        ):
            result_json = tool_fn.invoke(
                {"connection_id": 1, "table_names": ["orders"], "dimensions": ["region"]}
            )

        result = json.loads(result_json)
        assert result["success"] is True
        data_ctx = result["data_context"]

        # sources
        assert "orders" in data_ctx["sources"]
        assert data_ctx["sources"]["orders"]["connectionId"] == 1
        assert data_ctx["sources"]["orders"]["table"] == "public.orders"

        # baseJoin
        assert data_ctx["baseJoin"]["connectionId"] == 1
        assert "orders" in data_ctx["baseJoin"]["from"]

        # dimensions
        assert "region" in data_ctx["dimensions"]
        dim = data_ctx["dimensions"]["region"]
        assert dim["column"] == "region"
        assert dim["type"] == "varchar"

    def test_profiling_not_ready_returns_error(self):
        """Connection with profiling_status != 'ready' produces a failure message."""
        context = _make_context()
        conn = _make_connection(profiling_status="in_progress")
        factory, session = _make_db_session_factory(conn)
        tool_fn = _build_dashboard_context_tool(context, factory)

        result_json = tool_fn.invoke(
            {"connection_id": 1, "table_names": ["orders"], "dimensions": ["region"]}
        )

        result = json.loads(result_json)
        assert result["success"] is False
        assert "still being profiled" in result["message"]

    def test_connection_not_found_returns_error(self):
        """Database query returning None produces a 'not found' failure."""
        context = _make_context()
        factory, session = _make_db_session_factory(connection=None)
        tool_fn = _build_dashboard_context_tool(context, factory)

        result_json = tool_fn.invoke(
            {"connection_id": 1, "table_names": ["orders"], "dimensions": ["region"]}
        )

        result = json.loads(result_json)
        assert result["success"] is False
        assert "not found" in result["message"]

    def test_unauthorized_connection_returns_error(self):
        """Connection ID not in available_connections produces an 'not authorized' failure."""
        context = _make_context(connections=[99])  # connection 1 not authorized
        factory, session = _make_db_session_factory(_make_connection())
        tool_fn = _build_dashboard_context_tool(context, factory)

        result_json = tool_fn.invoke(
            {"connection_id": 1, "table_names": ["orders"], "dimensions": ["region"]}
        )

        result = json.loads(result_json)
        assert result["success"] is False
        assert "not authorized" in result["message"]

    def test_missing_table_returns_error_with_available_list(self):
        """Requesting a nonexistent table lists available tables in the error."""
        context = _make_context()
        factory, session = _make_db_session_factory(_make_connection())
        tool_fn = _build_dashboard_context_tool(context, factory)

        with patch(
            "backend.services.connection_context.load_context_file",
            return_value=SAMPLE_CONN_CONTEXT,
        ):
            result_json = tool_fn.invoke(
                {"connection_id": 1, "table_names": ["nonexistent"], "dimensions": ["region"]}
            )

        result = json.loads(result_json)
        assert result["success"] is False
        assert "nonexistent" in result["message"]
        # Available tables should be listed
        assert "customers" in result["message"]
        assert "orders" in result["message"]

    def test_missing_dimension_returns_error_with_available_list(self):
        """Requesting a nonexistent dimension lists available dimensions in the error."""
        context = _make_context()
        factory, session = _make_db_session_factory(_make_connection())
        tool_fn = _build_dashboard_context_tool(context, factory)

        with patch(
            "backend.services.connection_context.load_context_file",
            return_value=SAMPLE_CONN_CONTEXT,
        ):
            result_json = tool_fn.invoke(
                {"connection_id": 1, "table_names": ["orders"], "dimensions": ["nonexistent"]}
            )

        result = json.loads(result_json)
        assert result["success"] is False
        assert "nonexistent" in result["message"]
        # Available dimensions from orders table should be listed
        assert "region" in result["message"]
        assert "order_date" in result["message"]

    def test_basejoin_includes_correct_join_clauses(self):
        """With orders+customers, the baseJoin has a LEFT JOIN for customers via the relationship."""
        context = _make_context()
        factory, session = _make_db_session_factory(_make_connection())
        tool_fn = _build_dashboard_context_tool(context, factory)

        with patch(
            "backend.services.connection_context.load_context_file",
            return_value=SAMPLE_CONN_CONTEXT,
        ):
            result_json = tool_fn.invoke(
                {
                    "connection_id": 1,
                    "table_names": ["orders", "customers"],
                    "dimensions": ["region", "segment"],
                }
            )

        result = json.loads(result_json)
        assert result["success"] is True
        joins = result["data_context"]["baseJoin"]["joins"]
        assert len(joins) == 1

        join_clause = joins[0]
        assert "LEFT JOIN" in join_clause
        assert "customers" in join_clause
        # The relationship is orders.customer_id -> customers.id
        assert "customer_id" in join_clause
        assert ".id" in join_clause

    def test_basejoin_warns_when_no_relationship_found(self):
        """Two tables with no relationship produce a WARNING comment in the JOIN clause."""
        # Use a context with no relationships
        conn_context_no_rels = {
            "connectionId": 1,
            "tables": {
                "orders": {
                    "schema": "public",
                    "rowCount": 100,
                    "columns": {
                        "id": {"type": "integer", "role": "key"},
                        "region": {"type": "varchar", "role": "dimension", "cardinality": 5},
                    },
                },
                "products": {
                    "schema": "public",
                    "rowCount": 30,
                    "columns": {
                        "id": {"type": "integer", "role": "key"},
                        "category": {"type": "varchar", "role": "dimension", "cardinality": 8},
                    },
                },
            },
            "relationships": [],  # No relationships
        }

        context = _make_context()
        factory, session = _make_db_session_factory(_make_connection())
        tool_fn = _build_dashboard_context_tool(context, factory)

        with patch(
            "backend.services.connection_context.load_context_file",
            return_value=conn_context_no_rels,
        ):
            result_json = tool_fn.invoke(
                {
                    "connection_id": 1,
                    "table_names": ["orders", "products"],
                    "dimensions": ["region", "category"],
                }
            )

        result = json.loads(result_json)
        assert result["success"] is True
        joins = result["data_context"]["baseJoin"]["joins"]
        assert len(joins) == 1
        assert "WARNING" in joins[0]
        assert "products" in joins[0]

    def test_table_aliases_are_unique(self):
        """Tables 'orders' and 'options' both start with 'o' but get different aliases."""
        conn_context = {
            "connectionId": 1,
            "tables": {
                "orders": {
                    "schema": "public",
                    "rowCount": 100,
                    "columns": {
                        "id": {"type": "integer", "role": "key"},
                        "region": {"type": "varchar", "role": "dimension", "cardinality": 5},
                    },
                },
                "options": {
                    "schema": "public",
                    "rowCount": 20,
                    "columns": {
                        "id": {"type": "integer", "role": "key"},
                        "label": {"type": "varchar", "role": "dimension", "cardinality": 10},
                    },
                },
            },
            "relationships": [],
        }

        context = _make_context()
        factory, session = _make_db_session_factory(_make_connection())
        tool_fn = _build_dashboard_context_tool(context, factory)

        with patch(
            "backend.services.connection_context.load_context_file",
            return_value=conn_context,
        ):
            result_json = tool_fn.invoke(
                {
                    "connection_id": 1,
                    "table_names": ["orders", "options"],
                    "dimensions": ["region", "label"],
                }
            )

        result = json.loads(result_json)
        assert result["success"] is True
        data_ctx = result["data_context"]

        # Extract the aliases from the baseJoin "from" and the dimension alias references
        from_clause = data_ctx["baseJoin"]["from"]
        # The first table's alias is in the from clause (e.g., "orders o")
        parts = from_clause.split()
        first_alias = parts[1] if len(parts) > 1 else parts[0]

        # The second table's alias appears in the dimension or the join warning
        region_alias = data_ctx["dimensions"]["region"]["alias"].split(".")[0]
        label_alias = data_ctx["dimensions"]["label"]["alias"].split(".")[0]

        # Aliases must differ
        assert region_alias != label_alias

    def test_dimension_output_includes_cardinality(self):
        """Region dimension includes cardinality from the connection context."""
        context = _make_context()
        factory, session = _make_db_session_factory(_make_connection())
        tool_fn = _build_dashboard_context_tool(context, factory)

        with patch(
            "backend.services.connection_context.load_context_file",
            return_value=SAMPLE_CONN_CONTEXT,
        ):
            result_json = tool_fn.invoke(
                {"connection_id": 1, "table_names": ["orders"], "dimensions": ["region"]}
            )

        result = json.loads(result_json)
        assert result["success"] is True
        dim = result["data_context"]["dimensions"]["region"]
        assert dim["cardinality"] == 5
