"""Hand-written guidance for the chart widget type."""

CHART_GUIDANCE = """### Chart Type Selection

| Data pattern | Best type | Key options | Max width |
|---|---|---|---|
| Categories < 8 | bar or pie | `sortBy: "value"` | w=6 or w=8 |
| Categories 8-20 | bar | `indexAxis: "y"` (horizontal) | w=6 or w=8 |
| Categories > 20 | bar + LIMIT in SQL | `sortBy: "value"` | w=6 or w=8 |
| Composition | bar | `stacked: true` | w=6 or w=8 |
| Trend over time | line or area | — | w=6, w=8, or w=12 |
| Part-of-whole < 8 | pie or doughnut | `showValues: true` | w=4 or w=6 (NEVER w=12) |
| Correlation (x vs y) | scatter | `showLegend: false` if single dataset | w=6 or w=8 |

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

### SQL Patterns

**Bar/pie (categorical):**
```sql
SELECT category, COUNT(*) AS count
FROM orders
GROUP BY category
ORDER BY count DESC
LIMIT 10
```
Mapping: `{"type": "chart", "labelColumn": "category", "datasetColumns": [{"column": "count", "label": "Orders"}]}`

**Line/area (time-series):**
```sql
SELECT month, SUM(revenue) AS revenue, SUM(costs) AS costs
FROM financials
GROUP BY month
ORDER BY month
```
Mapping: `{"type": "chart", "labelColumn": "month", "datasetColumns": [{"column": "revenue", "label": "Revenue"}, {"column": "costs", "label": "Costs"}]}`

**Multi-dataset (stacked):**
```sql
SELECT region, product_type, SUM(sales) AS sales
FROM orders
GROUP BY region, product_type
```
Use one datasetColumn per series. Set `options.stacked: true`.
"""
