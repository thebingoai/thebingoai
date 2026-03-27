"""
Widget spec registry and renderer.

Combines auto-generated field documentation from JSON schemas
with hand-written guidance to produce complete widget specs.
"""

import json
from pathlib import Path
from typing import Optional

_SCHEMAS_DIR = Path(__file__).parent / "schemas"
_WIDGET_TYPES = ["kpi", "chart", "table", "filter", "text"]

# Cache rendered specs at module load time
_spec_cache: dict[str, str] = {}


def load_schema(widget_type: str) -> dict:
    """Load a JSON schema file for a widget type."""
    schema_path = _SCHEMAS_DIR / f"{widget_type}.json"
    with open(schema_path) as f:
        return json.load(f)


def _render_field(name: str, field: dict, indent: int = 0) -> str:
    """Render a single field definition as a markdown bullet."""
    prefix = "  " * indent
    type_str = field.get("type", "any")
    required = field.get("required", False)
    description = field.get("description", "")
    req_tag = " **(required)**" if required else ""

    # Enum values
    values = field.get("values")
    if values:
        type_str = " | ".join(f'`"{v}"`' for v in values)

    # Nested object with fields
    nested_fields = field.get("fields")
    if nested_fields:
        line = f"{prefix}- `{name}` (object{req_tag}): {description}\n"
        for sub_name, sub_field in nested_fields.items():
            line += _render_field(sub_name, sub_field, indent + 1)
        return line

    # Array with item schema
    items = field.get("items")
    if items and isinstance(items, dict) and any(
        isinstance(v, dict) for v in items.values()
    ):
        line = f"{prefix}- `{name}` (array{req_tag}): {description}\n"
        for sub_name, sub_field in items.items():
            if isinstance(sub_field, dict):
                line += _render_field(sub_name, sub_field, indent + 1)
            else:
                line += f"{prefix}  - `{sub_name}`: {sub_field}\n"
        return line

    return f"{prefix}- `{name}` ({type_str}{req_tag}): {description}\n"


def render_fields(schema: dict) -> str:
    """Auto-generate markdown field documentation from a JSON schema."""
    widget_type = schema.get("widget_type", "unknown")
    lines = [f"## {widget_type.upper()} Widget Configuration\n"]

    # Config fields
    config = schema.get("config", {})
    if config:
        lines.append("### Config Fields (`widget.config`)\n")
        for name, field in config.items():
            lines.append(_render_field(name, field))

    # Mapping fields
    mapping = schema.get("mapping", {})
    if mapping:
        lines.append("\n### DataSource Mapping (`dataSource.mapping`)\n")
        lines.append(f'Set `"type": "{widget_type}"` in the mapping object.\n\n')
        for name, field in mapping.items():
            lines.append(_render_field(name, field))

    # Position defaults
    pos = schema.get("position_defaults", {})
    if pos:
        parts = [f"{k}={v}" for k, v in pos.items()]
        lines.append(f"\n### Position Defaults\n{', '.join(parts)}\n")

    return "".join(lines)


def _build_spec(widget_type: str) -> str:
    """Build a complete spec by combining auto-generated fields + guidance."""
    schema = load_schema(widget_type)
    fields_section = render_fields(schema)

    # Lazy import to avoid circular imports at module level
    from backend.agents.dashboard_agent.widget_specs.guidance import GUIDANCE

    guidance = GUIDANCE.get(widget_type, "")
    return f"{fields_section}\n{guidance}"


def _warm_cache() -> None:
    """Pre-render all widget specs into the cache."""
    for wt in _WIDGET_TYPES:
        try:
            _spec_cache[wt] = _build_spec(wt)
        except Exception:
            pass  # Logged at call time if needed


def get_widget_spec(widget_type: str) -> Optional[str]:
    """
    Get the complete rendered specification for a widget type.

    Returns the combined auto-generated field docs + hand-written guidance,
    or None if the widget type is unknown.
    """
    if not _spec_cache:
        _warm_cache()

    return _spec_cache.get(widget_type)


def get_available_types() -> list[str]:
    """Return the list of supported widget types."""
    return list(_WIDGET_TYPES)
