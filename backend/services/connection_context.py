"""Connection Context — builds, saves, and loads per-connection data contexts.

A data context is a structured description of a connection's tables, columns
(with inferred roles), and relationships.  It is built once during profiling
and consumed by the dashboard agent to assemble dashboard-level contexts.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict

from backend.config import settings
from backend.services.table_profiler import NUMERIC_TYPES, DATE_TYPES

logger = logging.getLogger(__name__)

CONTEXTS_DIR = os.path.join(os.path.dirname(settings.schemas_dir), "contexts")

# ---------------------------------------------------------------------------
# Role inference
# ---------------------------------------------------------------------------

_DIMENSION_CARDINALITY_THRESHOLD = 50


def infer_column_role(
    col_name: str,
    col_type_raw: str,
    profile: Dict[str, Any] | None,
    *,
    is_primary_key: bool = False,
    nullable: bool = True,
) -> str:
    """Infer a semantic role for a column based on type and profile stats.

    Returns one of: "key", "dimension", "measure", "attribute".
    """
    col_type = col_type_raw.split("(")[0].strip().lower()

    # Explicit primary keys are always "key"
    if is_primary_key:
        return "key"

    # Date/time columns are always "dimension" (temporal)
    if col_type in DATE_TYPES:
        return "dimension"

    # Numeric columns
    if col_type in NUMERIC_TYPES:
        # Foreign-key-like naming convention → key
        if col_name.lower().endswith("_id") or col_name.lower() == "id":
            return "key"
        return "measure"

    # Text/categorical columns — use cardinality from profile
    if profile:
        cardinality = profile.get("distinct_count", 0)
        if cardinality > 0 and cardinality <= _DIMENSION_CARDINALITY_THRESHOLD:
            return "dimension"
        if cardinality > _DIMENSION_CARDINALITY_THRESHOLD:
            return "attribute"

    # Fallback: low-ish cardinality name heuristics
    if col_name.lower().endswith(("_type", "_status", "_category", "_code")):
        return "dimension"

    return "attribute"


# ---------------------------------------------------------------------------
# Relationship inference
# ---------------------------------------------------------------------------

_FK_NAME_RE = re.compile(r"^(.+?)_id$", re.IGNORECASE)


def infer_relationships_from_naming(
    tables: Dict[str, dict],
    existing_relationships: list[dict],
) -> list[dict]:
    """Supplement FK-based relationships with naming-convention matches.

    For each column like ``customer_id``, if a table named ``customers`` (or
    ``customer``) exists and has a column ``id``, we add a relationship unless
    one already exists between those endpoints.
    """
    existing_pairs = {
        (r["from"], r["to"]) for r in existing_relationships
    }

    table_name_lookup: dict[str, str] = {}  # lowercase → actual name
    for tname in tables:
        table_name_lookup[tname.lower()] = tname

    new_rels: list[dict] = []

    for tname, tdata in tables.items():
        for col in tdata.get("columns", []):
            cname = col if isinstance(col, str) else col.get("name", "")
            m = _FK_NAME_RE.match(cname)
            if not m:
                continue
            ref_stem = m.group(1).lower()
            # Try plural and singular forms
            for candidate in (ref_stem + "s", ref_stem):
                actual = table_name_lookup.get(candidate)
                if actual and actual != tname:
                    pair = (f"{tname}.{cname}", f"{actual}.id")
                    if pair not in existing_pairs:
                        new_rels.append({
                            "from": pair[0],
                            "to": pair[1],
                            "type": "many_to_one",
                            "inferred": True,
                        })
                        existing_pairs.add(pair)
                    break

    return new_rels


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------

def build_connection_context(
    connection_id: int,
    schema_json: Dict[str, Any],
    table_profiles: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a connection data context from schema + profiling results.

    Args:
        connection_id: The database connection ID.
        schema_json: Output of ``schema_discovery.load_schema_file()``.
        table_profiles: ``{table_name: profile_table() output}`` for all
            tables that were profiled.

    Returns:
        Structured data context dict ready for persistence.
    """
    tables_out: Dict[str, Any] = {}

    # Iterate over all schemas and tables in the discovered schema
    for schema_name, schema_data in schema_json.get("schemas", {}).items():
        for table_name, table_data in schema_data.get("tables", {}).items():
            columns_out: Dict[str, Any] = {}
            raw_columns = table_data.get("columns", [])
            profile = table_profiles.get(table_name, {})
            profile_columns = profile.get("columns", {})

            for col in raw_columns:
                cname = col["name"] if isinstance(col, dict) else col
                ctype = col.get("type", "text") if isinstance(col, dict) else "text"
                is_pk = col.get("primary_key", False) if isinstance(col, dict) else False
                nullable = col.get("nullable", True) if isinstance(col, dict) else True

                col_profile = profile_columns.get(cname)
                role = infer_column_role(
                    cname, ctype, col_profile,
                    is_primary_key=is_pk, nullable=nullable,
                )

                col_out: Dict[str, Any] = {
                    "type": ctype,
                    "role": role,
                    "nullable": nullable,
                }

                # Merge profile stats into the column entry
                if col_profile and "error" not in col_profile:
                    if col_profile.get("type") == "numeric":
                        for k in ("min", "max", "avg"):
                            if col_profile.get(k) is not None:
                                col_out[k] = col_profile[k]
                    elif col_profile.get("type") == "date":
                        for k in ("min", "max"):
                            if col_profile.get(k) is not None:
                                col_out[k] = col_profile[k]
                    elif col_profile.get("type") == "categorical":
                        if col_profile.get("distinct_count") is not None:
                            col_out["cardinality"] = col_profile["distinct_count"]
                        if col_profile.get("top_values"):
                            col_out["topValues"] = col_profile["top_values"]

                columns_out[cname] = col_out

            tables_out[table_name] = {
                "schema": schema_name,
                "rowCount": table_data.get("row_count", 0),
                "columns": columns_out,
            }

    # Relationships — combine FK-based + naming-convention-inferred
    fk_relationships = schema_json.get("relationships", [])
    inferred_rels = infer_relationships_from_naming(tables_out, fk_relationships)
    all_relationships = fk_relationships + inferred_rels

    return {
        "connectionId": connection_id,
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "tables": tables_out,
        "relationships": all_relationships,
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_context_file(connection_id: int, context: Dict[str, Any]) -> str:
    """Save connection context to JSON file. Returns the file path."""
    os.makedirs(CONTEXTS_DIR, exist_ok=True)
    file_path = os.path.join(CONTEXTS_DIR, f"{connection_id}_context.json")
    with open(file_path, "w") as f:
        json.dump(context, f, indent=2)
    logger.info("Connection context saved to %s", file_path)
    return file_path


def load_context_file(connection_id: int) -> Dict[str, Any]:
    """Load connection context from JSON file.

    Raises FileNotFoundError if the context has not been built yet.
    """
    file_path = os.path.join(CONTEXTS_DIR, f"{connection_id}_context.json")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Context file not found: {file_path}")
    with open(file_path, "r") as f:
        return json.load(f)


def delete_context_file(connection_id: int) -> bool:
    """Delete connection context file. Returns True if deleted."""
    file_path = os.path.join(CONTEXTS_DIR, f"{connection_id}_context.json")
    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info("Deleted context file: %s", file_path)
        return True
    return False
