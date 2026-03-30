"""Tests for dimension-aware filter injection in backend.api.widget_data."""
import pytest

from backend.api.widget_data import _dimension_applies_to_sources, inject_filters
from backend.schemas.widget_data import FilterParam


# ---------------------------------------------------------------------------
# TestDimensionAppliesToSources
# ---------------------------------------------------------------------------

class TestDimensionAppliesToSources:
    """Tests for _dimension_applies_to_sources — pure function."""

    def test_matching_dimension_and_source_returns_true(self):
        ctx = {"dimensions": {"region": {"column": "region", "sources": ["orders"]}}}
        assert _dimension_applies_to_sources("region", ctx, ["orders"]) is True

    def test_no_source_overlap_returns_false(self):
        ctx = {"dimensions": {"region": {"column": "region", "sources": ["orders"]}}}
        assert _dimension_applies_to_sources("region", ctx, ["payments"]) is False

    def test_unknown_dimension_returns_true(self):
        """Backward compat: columns not in the context are assumed applicable."""
        ctx = {"dimensions": {"region": {"column": "region", "sources": ["orders"]}}}
        assert _dimension_applies_to_sources("unknown_col", ctx, ["orders"]) is True

    def test_empty_dimensions_dict_returns_true(self):
        ctx = {"dimensions": {}}
        assert _dimension_applies_to_sources("anything", ctx, ["orders"]) is True

    def test_multiple_sources_partial_overlap_returns_true(self):
        ctx = {"dimensions": {"region": {"column": "region", "sources": ["orders", "customers"]}}}
        assert _dimension_applies_to_sources("region", ctx, ["customers", "payments"]) is True

    def test_dimension_with_no_sources_returns_false(self):
        ctx = {"dimensions": {"region": {"column": "region", "sources": []}}}
        assert _dimension_applies_to_sources("region", ctx, ["orders"]) is False


# ---------------------------------------------------------------------------
# TestInjectFiltersWithContext
# ---------------------------------------------------------------------------

class TestInjectFiltersWithContext:
    """Tests for inject_filters with dimension-aware mode."""

    def _ctx(self):
        return {
            "dimensions": {
                "region": {"column": "region", "sources": ["orders"]},
                "order_date": {"column": "order_date", "sources": ["orders"]},
            },
        }

    def test_filters_only_applicable_dimensions(self):
        """Widget from 'orders' gets the region filter applied."""
        sql = "SELECT * FROM orders o"
        filters = [FilterParam(column="region", op="eq", value="US")]
        result_sql, params = inject_filters(sql, filters, data_context=self._ctx(), widget_sources=["orders"])

        assert '"region" = %(_f0)s' in result_sql
        assert params["_f0"] == "US"

    def test_skips_filter_for_non_overlapping_source(self):
        """Widget from 'payments' doesn't get region filter (region is orders-only)."""
        sql = "SELECT * FROM payments p"
        filters = [FilterParam(column="region", op="eq", value="US")]
        result_sql, params = inject_filters(sql, filters, data_context=self._ctx(), widget_sources=["payments"])

        assert result_sql == "SELECT * FROM payments p"
        assert params == {}

    def test_all_filters_skipped_returns_original_sql(self):
        sql = "SELECT SUM(amount) FROM payments"
        filters = [
            FilterParam(column="region", op="eq", value="US"),
            FilterParam(column="order_date", op="gte", value="2024-01-01"),
        ]
        result_sql, params = inject_filters(sql, filters, data_context=self._ctx(), widget_sources=["payments"])

        assert result_sql == sql
        assert params == {}

    def test_no_context_falls_back_to_legacy(self):
        """Without data_context, all filters are injected (legacy behavior)."""
        sql = "SELECT * FROM payments"
        filters = [FilterParam(column="region", op="eq", value="US")]
        result_sql, params = inject_filters(sql, filters, data_context=None, widget_sources=None)

        assert '"region" = %(_f0)s' in result_sql
        assert params["_f0"] == "US"

    def test_no_widget_sources_falls_back_to_legacy(self):
        """Without widget_sources, all filters are injected."""
        sql = "SELECT * FROM payments"
        filters = [FilterParam(column="region", op="eq", value="US")]
        result_sql, params = inject_filters(sql, filters, data_context=self._ctx(), widget_sources=None)

        assert '"region" = %(_f0)s' in result_sql

    def test_mixed_applicable_and_inapplicable_filters(self):
        """Widget from both sources gets region, but unknown_col is also applied (fallback)."""
        sql = "SELECT * FROM orders o JOIN payments p ON o.id = p.order_id"
        filters = [
            FilterParam(column="region", op="eq", value="US"),       # orders → applies
            FilterParam(column="unknown", op="eq", value="test"),    # not in context → applies (fallback)
        ]
        result_sql, params = inject_filters(
            sql, filters,
            data_context=self._ctx(), widget_sources=["orders", "payments"],
        )

        # region applies (widget has orders source)
        assert '"region"' in result_sql
        # unknown applies (not in dimensions → backward compat)
        assert '"unknown"' in result_sql
        assert len(params) == 2

    def test_in_operator_with_context(self):
        sql = "SELECT * FROM orders"
        filters = [FilterParam(column="region", op="in", value=["US", "UK"])]
        result_sql, params = inject_filters(sql, filters, data_context=self._ctx(), widget_sources=["orders"])

        assert '"region" IN' in result_sql
        assert params["_f0_0"] == "US"
        assert params["_f0_1"] == "UK"

    def test_context_with_empty_filter_list(self):
        sql = "SELECT * FROM orders"
        result_sql, params = inject_filters(sql, [], data_context=self._ctx(), widget_sources=["orders"])
        assert result_sql == sql
        assert params == {}
