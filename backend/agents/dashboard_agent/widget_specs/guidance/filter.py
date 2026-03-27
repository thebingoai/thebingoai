"""Hand-written guidance for the filter widget type."""

FILTER_GUIDANCE = """### Key Rules

- Filter widgets have **NO dataSource** — controls are statically defined
- **Every control MUST have a `column` field** — the real DB column name used for SQL WHERE clauses
- **Dropdown controls MUST have `optionsSource`** with connectionId and SQL query

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
          "optionsSource": {
            "connectionId": 1,
            "sql": "SELECT DISTINCT region AS option_value FROM sales ORDER BY 1 LIMIT 50"
          }
        },
        {
          "type": "date_range",
          "label": "Date",
          "key": "date",
          "column": "transaction_date"
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

### Best Practices

- Place at y=2, w=12, h=2 (Section 2 — Filters)
- Include 2-4 controls for key slicing dimensions
- Use dropdown for categorical columns with reasonable cardinality
- Use date_range for time columns
- Use search for free-text filtering (names, descriptions)
- optionsSource SQL should always use `AS option_value` alias, ORDER BY, and LIMIT 50
"""
