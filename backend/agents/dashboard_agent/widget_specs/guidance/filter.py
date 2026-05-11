"""Hand-written guidance for the filter widget type."""

FILTER_GUIDANCE = """### Key Rules

- Filter widgets have **NO dataSource** — controls are statically defined
- **Every control MUST have both `column` and `dimension` fields**:
  - `column`: the real DB column name used for SQL WHERE clauses
  - `dimension`: references a dimension from the dashboard data context (from `build_dashboard_context`)
- **Dropdown controls MUST have `optionsSource`** with connectionId and SQL query
- **Filter dimensions MUST be reachable by ALL data widgets** — this is why every widget uses the baseJoin

### Example Configuration

```json
{
  "id": "filter_bar",
  "position": {"x": 0, "y": 2, "w": 12, "h": 2},
  "widget": {
    "type": "filter",
    "config": {
      "controls": [
        {
          "type": "dropdown",
          "label": "Region",
          "key": "region",
          "column": "region",
          "dimension": "region",
          "optionsSource": {
            "connectionId": 1,
            "sql": "SELECT DISTINCT o.region AS option_value FROM orders o ORDER BY 1"
          }
        },
        {
          "type": "date_range",
          "label": "Date",
          "key": "date",
          "column": "order_date",
          "dimension": "order_date",
          "dateRangeSource": {
            "connectionId": 1,
            "sql": "SELECT MIN(o.order_date) AS min_date, MAX(o.order_date) AS max_date FROM orders o"
          }
        },
        {
          "type": "search",
          "label": "Search",
          "key": "search",
          "column": "name"
        }
      ]
    }
  }
}
```

### Date Range Source

- **date_range controls should include `dateRangeSource`** so the frontend can query the actual min/max dates from the data instead of defaulting to today
- The SQL must return exactly two columns: `min_date` and `max_date`
- Example SQL: `SELECT MIN(o.order_date) AS min_date, MAX(o.order_date) AS max_date FROM orders o`
- Both `min_date` and `max_date` are required — the frontend uses `max_date` to compute the default "to" date and `min_date` to clamp the "from" date
- Use the same baseJoin aliases as other widget queries (e.g., `o.order_date`)

### Best Practices

- Place at y=2, w=12, h=2 (Section 2 — Filters)
- Include 2-4 controls for key slicing dimensions from the data context
- Use dropdown for categorical dimensions with reasonable cardinality
- Use date_range for temporal dimensions
- Use search for free-text filtering (names, descriptions)
- optionsSource SQL should use the baseJoin aliases (e.g., `o.region`) and ORDER BY
- Every dimension you use as a filter must be included in the `build_dashboard_context` call
"""
