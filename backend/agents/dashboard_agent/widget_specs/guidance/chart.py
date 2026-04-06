"""Hand-written guidance for the chart widget type."""

CHART_GUIDANCE = """### Chart Type Selection

| Data pattern | Best type | Key options | Max width |
|---|---|---|---|
| Categories < 8 | bar or pie | `sortBy: "value"` | w=6 or w=8 |
| Categories 8-20 | bar | `indexAxis: "y"` (horizontal) | w=6 or w=8 |
| Categories > 20 | bar | `sortBy: "value"` | w=6 or w=8 |
| Composition | bar | `stacked: true` | w=6 or w=8 |
| Trend over time | line or area | — | w=6, w=8, or w=12 |
| Part-of-whole < 8 | pie or doughnut | `showValues: true` | w=4 or w=6 (NEVER w=12) |
| Correlation (x vs y) | scatter | `showLegend: true` for grouped scatter | w=6 or w=8 |

### Layout Rules

- Use **at least 2-3 different chart types** per dashboard
- Pie/doughnut charts are **NEVER full-width** — max w=6
- Default to w=6 and pair charts side-by-side at the same y row
- w=12 ONLY for time-series line/area charts
- Place charts in Section 3 (Analysis & Trends, y=5 to y=14)

### Options Best Practices

- **Bar charts**: set `sortBy: "value", sortDirection: "desc"` unless x-axis is temporal
- **Horizontal bars**: use `indexAxis: "y"` for long category labels or 8+ categories
- **Pie/doughnut**: always set `showValues: true` so slice values are visible
- **Single-dataset charts**: hide legend with `showLegend: false` to reduce clutter
- **Stacked charts**: use for composition comparison across categories
- Skip animation config unless specifically requested — defaults are sensible

### SQL Patterns (use baseJoin from data context)

IMPORTANT: Every chart must include the baseJoin from the dashboard data context so that
dashboard filters can reach all dimensions. Use table aliases from the baseJoin.

**Bar/pie (categorical) with baseJoin:**
```sql
SELECT o.category, COUNT(*) AS count
FROM orders o
LEFT JOIN payments p ON o.id = p.order_id
GROUP BY o.category
ORDER BY count DESC
```
Mapping: `{"type": "chart", "labelColumn": "category", "datasetColumns": [{"column": "count", "label": "Orders"}]}`

**Line/area (time-series) with baseJoin:**
```sql
SELECT o.month, SUM(o.revenue) AS revenue, SUM(o.costs) AS costs
FROM orders o
LEFT JOIN payments p ON o.id = p.order_id
GROUP BY o.month
ORDER BY o.month
```
Mapping: `{"type": "chart", "labelColumn": "month", "datasetColumns": [{"column": "revenue", "label": "Revenue"}, {"column": "costs", "label": "Costs"}]}`

**Multi-dataset (stacked) with baseJoin:**
```sql
SELECT o.region, o.product_type, SUM(o.sales) AS sales
FROM orders o
LEFT JOIN payments p ON o.id = p.order_id
GROUP BY o.region, o.product_type
```
Use one datasetColumn per series. Set `options.stacked: true`.

**Scatter (correlation) with baseJoin:**
```sql
SELECT o.metric_x, o.metric_y, o.category
FROM orders o
LEFT JOIN payments p ON o.id = p.order_id
WHERE o.metric_x IS NOT NULL AND o.metric_y IS NOT NULL
```
Scatter mapping rules:
- `labelColumn`: the grouping column (e.g. category/team) — points are grouped into one dataset per unique value
- `datasetColumns`: exactly 2 entries — label them with `(X)` and `(Y)` suffixes so the backend maps axes correctly
- `chartType`: **must** be set to `"scatter"` in the mapping

Mapping: `{"type": "chart", "chartType": "scatter", "labelColumn": "category", "datasetColumns": [{"column": "metric_x", "label": "Metric X (X)"}, {"column": "metric_y", "label": "Metric Y (Y)"}]}`
"""
