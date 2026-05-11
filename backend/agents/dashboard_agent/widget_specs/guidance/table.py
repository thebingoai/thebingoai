"""Hand-written guidance for the table widget type."""

TABLE_GUIDANCE = """### Column Formatting

Always set `format` on columns that contain:
- **Monetary values**: use `"currency"` — auto-formats with currency symbol
- **Percentages/rates**: use `"percent"` — auto-applies red/green coloring based on positive/negative
- **Dates**: use `"date"` — auto-formats to readable date
- **Numbers**: use `"number"` — auto-formats with thousand separators

### SQL Patterns

**Detail table:**
```sql
SELECT name, email, created_at, total_spent, conversion_rate
FROM customers
ORDER BY total_spent DESC
LIMIT 100
```
Mapping:
```json
{
  "type": "table",
  "columnConfig": [
    {"column": "name", "label": "Customer", "sortable": true},
    {"column": "email", "label": "Email"},
    {"column": "created_at", "label": "Joined", "sortable": true, "format": "date"},
    {"column": "total_spent", "label": "Total Spent", "sortable": true, "format": "currency"},
    {"column": "conversion_rate", "label": "Conv. Rate", "format": "percent"}
  ]
}
```

### Best Practices

- Place tables in Section 4 (Detail & Drill-Down, y=16+)
- Default width w=12, h=5
- Always use LIMIT in SQL to avoid sending thousands of rows
- Make key columns sortable for interactive exploration
- Set format on every column that isn't plain text — it significantly improves readability
"""
