"""Tests for backend.services.connection_context — role inference, relationship inference, context building."""
from unittest.mock import MagicMock

import pytest

from backend.services.connection_context import (
    infer_column_role,
    infer_relationships_from_naming,
    build_connection_context,
    save_connection_context,
    load_connection_context,
    delete_connection_context,
)


# ---------------------------------------------------------------------------
# TestInferColumnRole
# ---------------------------------------------------------------------------

class TestInferColumnRole:
    """Tests for infer_column_role — pure function, no I/O."""

    def test_primary_key_always_returns_key(self):
        assert infer_column_role("id", "integer", None, is_primary_key=True) == "key"

    def test_primary_key_overrides_date_type(self):
        assert infer_column_role("created_at", "timestamp", None, is_primary_key=True) == "key"

    def test_date_type_returns_dimension(self):
        assert infer_column_role("order_date", "date", None) == "dimension"

    def test_timestamp_type_returns_dimension(self):
        assert infer_column_role("created_at", "timestamp", None) == "dimension"

    def test_timestamp_with_tz_returns_dimension(self):
        assert infer_column_role("updated", "timestamp with time zone", None) == "dimension"

    def test_numeric_non_id_returns_measure(self):
        assert infer_column_role("amount", "numeric", None) == "measure"

    def test_integer_non_id_returns_measure(self):
        assert infer_column_role("quantity", "integer", None) == "measure"

    def test_column_ending_in_id_returns_key(self):
        assert infer_column_role("customer_id", "integer", None) == "key"

    def test_column_named_id_returns_key(self):
        assert infer_column_role("id", "integer", None) == "key"

    def test_text_low_cardinality_returns_dimension(self):
        profile = {"distinct_count": 10}
        assert infer_column_role("region", "varchar", profile) == "dimension"

    def test_text_high_cardinality_returns_attribute(self):
        profile = {"distinct_count": 200}
        assert infer_column_role("email", "varchar", profile) == "attribute"

    def test_text_cardinality_at_threshold_returns_dimension(self):
        profile = {"distinct_count": 50}
        assert infer_column_role("category", "varchar", profile) == "dimension"

    def test_text_cardinality_above_threshold_returns_attribute(self):
        profile = {"distinct_count": 51}
        assert infer_column_role("description", "varchar", profile) == "attribute"

    def test_text_no_profile_with_type_suffix_returns_dimension(self):
        assert infer_column_role("order_type", "varchar", None) == "dimension"

    def test_text_no_profile_with_status_suffix_returns_dimension(self):
        assert infer_column_role("order_status", "varchar", None) == "dimension"

    def test_text_no_profile_with_category_suffix_returns_dimension(self):
        assert infer_column_role("product_category", "varchar", None) == "dimension"

    def test_text_no_profile_no_suffix_returns_attribute(self):
        assert infer_column_role("description", "varchar", None) == "attribute"

    def test_varchar_with_size_parses_base_type(self):
        assert infer_column_role("notes", "varchar(255)", {"distinct_count": 1000}) == "attribute"

    def test_float_type_returns_measure(self):
        assert infer_column_role("price", "float", None) == "measure"

    def test_bigint_id_returns_key(self):
        assert infer_column_role("user_id", "bigint", None) == "key"


# ---------------------------------------------------------------------------
# TestInferRelationshipsFromNaming
# ---------------------------------------------------------------------------

class TestInferRelationshipsFromNaming:
    """Tests for infer_relationships_from_naming — pure function."""

    def test_customer_id_matches_customers_table(self):
        tables = {
            "orders": {"columns": [{"name": "customer_id"}]},
            "customers": {"columns": [{"name": "id"}]},
        }
        rels = infer_relationships_from_naming(tables, [])
        assert len(rels) == 1
        assert rels[0]["from"] == "orders.customer_id"
        assert rels[0]["to"] == "customers.id"
        assert rels[0]["inferred"] is True

    def test_order_id_matches_orders_table_singular(self):
        tables = {
            "payments": {"columns": [{"name": "order_id"}]},
            "orders": {"columns": [{"name": "id"}]},
        }
        rels = infer_relationships_from_naming(tables, [])
        assert len(rels) == 1
        assert rels[0]["from"] == "payments.order_id"
        assert rels[0]["to"] == "orders.id"

    def test_no_match_when_target_table_missing(self):
        tables = {
            "orders": {"columns": [{"name": "category_id"}]},
        }
        rels = infer_relationships_from_naming(tables, [])
        assert len(rels) == 0

    def test_skips_existing_fk_relationships(self):
        tables = {
            "orders": {"columns": [{"name": "customer_id"}]},
            "customers": {"columns": [{"name": "id"}]},
        }
        existing = [{"from": "orders.customer_id", "to": "customers.id"}]
        rels = infer_relationships_from_naming(tables, existing)
        assert len(rels) == 0  # No duplicates

    def test_self_referencing_column_ignored(self):
        """parent_id in 'parents' table should not create self-join."""
        tables = {
            "parents": {"columns": [{"name": "parent_id"}]},
        }
        rels = infer_relationships_from_naming(tables, [])
        assert len(rels) == 0

    def test_multiple_fk_columns_inferred(self):
        tables = {
            "orders": {"columns": [{"name": "customer_id"}, {"name": "product_id"}]},
            "customers": {"columns": [{"name": "id"}]},
            "products": {"columns": [{"name": "id"}]},
        }
        rels = infer_relationships_from_naming(tables, [])
        assert len(rels) == 2
        from_pairs = {(r["from"], r["to"]) for r in rels}
        assert ("orders.customer_id", "customers.id") in from_pairs
        assert ("orders.product_id", "products.id") in from_pairs


# ---------------------------------------------------------------------------
# TestBuildConnectionContext
# ---------------------------------------------------------------------------

class TestBuildConnectionContext:
    """Tests for build_connection_context — uses sample_schema_json fixture."""

    def test_builds_context_with_tables_columns_relationships(self, sample_schema_json):
        profiles = {
            "orders": {"table_name": "orders", "columns": {
                "region": {"type": "categorical", "distinct_count": 5, "top_values": ["US", "UK"]},
                "amount": {"type": "numeric", "min": 10, "max": 1000, "avg": 100},
            }},
            "customers": {"table_name": "customers", "columns": {}},
        }
        ctx = build_connection_context(1, sample_schema_json, profiles)

        assert ctx["connectionId"] == 1
        assert "orders" in ctx["tables"]
        assert "customers" in ctx["tables"]
        assert len(ctx["relationships"]) >= 1  # FK from schema

    def test_merges_profile_stats_into_columns(self, sample_schema_json):
        profiles = {
            "orders": {"table_name": "orders", "columns": {
                "region": {"type": "categorical", "distinct_count": 5, "top_values": ["US", "UK"]},
                "amount": {"type": "numeric", "min": 10, "max": 1000, "avg": 500},
                "order_date": {"type": "date", "min": "2023-01-01", "max": "2025-12-31"},
            }},
        }
        ctx = build_connection_context(1, sample_schema_json, profiles)
        orders = ctx["tables"]["orders"]

        assert orders["columns"]["region"]["cardinality"] == 5
        assert orders["columns"]["region"]["topValues"] == ["US", "UK"]
        assert orders["columns"]["amount"]["min"] == 10
        assert orders["columns"]["amount"]["max"] == 1000
        assert orders["columns"]["order_date"]["min"] == "2023-01-01"

    def test_handles_missing_profile_gracefully(self, sample_schema_json):
        """Tables without profiles should still have columns with inferred roles."""
        ctx = build_connection_context(1, sample_schema_json, {})
        orders = ctx["tables"]["orders"]

        assert "id" in orders["columns"]
        assert orders["columns"]["id"]["role"] == "key"  # primary_key=True
        assert orders["columns"]["order_date"]["role"] == "dimension"  # date type

    def test_infers_naming_relationships_added_to_fks(self, sample_schema_json):
        ctx = build_connection_context(1, sample_schema_json, {})
        # Schema already has FK: orders.customer_id → customers.id
        # Should be in relationships
        rel_pairs = {(r["from"], r["to"]) for r in ctx["relationships"]}
        assert ("orders.customer_id", "customers.id") in rel_pairs

    def test_context_has_correct_connection_id_and_timestamp(self, sample_schema_json):
        ctx = build_connection_context(42, sample_schema_json, {})
        assert ctx["connectionId"] == 42
        assert "builtAt" in ctx

    def test_column_roles_correctly_assigned(self, sample_schema_json):
        ctx = build_connection_context(1, sample_schema_json, {})
        orders = ctx["tables"]["orders"]

        assert orders["columns"]["id"]["role"] == "key"
        assert orders["columns"]["region"]["role"] in ("dimension", "attribute")  # No profile → heuristic
        assert orders["columns"]["amount"]["role"] == "measure"
        assert orders["columns"]["order_date"]["role"] == "dimension"
        assert orders["columns"]["customer_id"]["role"] == "key"


# ---------------------------------------------------------------------------
# TestConnectionContextDb
# ---------------------------------------------------------------------------

class TestConnectionContextDb:
    """Tests for save_connection_context / load_connection_context / delete_connection_context."""

    def test_save_issues_update_to_data_context_column(self):
        db = MagicMock()
        ctx = {"connectionId": 1, "tables": {"t1": {}}}

        save_connection_context(db, 1, ctx)

        update_call = db.query.return_value.filter.return_value.update
        update_call.assert_called_once_with({"data_context": ctx}, synchronize_session=False)

    def test_load_returns_payload_when_row_has_data_context(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = ({"tables": {"t1": {}}},)

        result = load_connection_context(db, 1)

        assert result == {"tables": {"t1": {}}}

    def test_load_returns_none_when_row_missing(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        assert load_connection_context(db, 999) is None

    def test_load_returns_none_when_data_context_is_null(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = (None,)

        assert load_connection_context(db, 1) is None

    def test_delete_nulls_column_and_reports_rowcount(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.update.return_value = 1

        assert delete_connection_context(db, 1) is True
        db.query.return_value.filter.return_value.update.assert_called_once_with(
            {"data_context": None}, synchronize_session=False
        )

    def test_delete_returns_false_when_no_row_updated(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.update.return_value = 0

        assert delete_connection_context(db, 999) is False
