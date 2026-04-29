"""Hand-written guidance for the filter widget type."""

FILTER_GUIDANCE = """### Key Rules

- Filter widgets have **NO dataSource** — controls are statically defined
- **Every control MUST have both `column` and `dimension` fields**:
  - `column`: the real DB column name used for SQL WHERE clauses
  - `dimension`: references a dimension from the dashboard data context (from `build_dashboard_context`)
- **Dropdown controls MUST have `optionsSource`** with connectionId and SQL query
- **Filter dimensions MUST be reachable by ALL data widgets** — this is why every widget uses the baseJoin
- **`date_range` controls MUST include `dateRangeSource`** (SQL returning `min_date`/`max_date`) and **`dateRangeDefault`** (one of `"full"`, `"7d"`, `"30d"`, `"90d"`, `"ytd"`)

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
          },
          "dateRangeDefault": "full"
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

### Date Range Default

Set `dateRangeDefault` on `date_range` controls to configure the initial range when the dashboard loads:

| Value | Meaning |
|-------|---------|
| `"full"` | `min_date → max_date` — shows all available data (recommended default for analytical/historical datasets) |
| `"7d"` | Last 7 days ending at `max_date` |
| `"30d"` | Last 30 days ending at `max_date` |
| `"90d"` | Last 90 days ending at `max_date` |
| `"ytd"` | Year-to-date — Jan 1 of `max_date`'s year through `max_date` |

- **Default when omitted:** `"full"` if `dateRangeSource` is present; `"7d"` from today if no `dateRangeSource`
- Use `"full"` for historical/analytical datasets where users want to explore all data
- Use `"7d"` / `"30d"` for live operational dashboards where recent activity matters most
- Use `"ytd"` for financial or business dashboards tracking year-to-date performance

### Best Practices

- Place at y=2, w=12, h=2 (Section 2 — Filters)
- Include 2-4 controls for key slicing dimensions from the data context
- Use dropdown for categorical dimensions with reasonable cardinality
- Use date_range for temporal dimensions
- Use search for free-text filtering (names, descriptions)
- optionsSource SQL should use the baseJoin aliases (e.g., `o.region`) and ORDER BY
- Every dimension you use as a filter must be included in the `build_dashboard_context` call
"""
