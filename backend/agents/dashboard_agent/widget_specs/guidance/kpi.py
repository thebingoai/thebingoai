"""Hand-written guidance for the KPI widget type."""

KPI_GUIDANCE = """### autoTrend vs Legacy Trend

**autoTrend: true (recommended):** SQL returns multiple time-ordered rows. The system automatically:
- Computes the headline value using the `aggregation` method (default: 'first')
- Derives trend direction and % change
- Populates the sparkline from all rows (value column as Y, row order as X)

**Trend calculation is controlled by `periodLabel`:**
- `"vs last period"` (or omitted) — compares the last 2 rows in query order (simplest)
- `"vs yesterday"` / `"vs last week"` / `"vs last month"` / `"vs last quarter"` / `"vs last year"` — **date-based**: buckets rows into current and previous period using `trendDateColumn`, aggregates each bucket with the KPI's `aggregation` method, and computes trend % from the two aggregated values. **Requires `trendDateColumn`.**

**Legacy (use only when you need full control):** Manually specify separate columns:
- `trendValueColumn` — a pre-computed trend number in the SQL output
- `sparklineXColumn` / `sparklineYColumn` — explicit sparkline axes
- `sparklineSortColumn` / `sparklineSortDirection` — row ordering for sparkline

### SQL Patterns (use baseJoin from data context)

IMPORTANT: Every KPI must include the baseJoin from the dashboard data context so that
dashboard filters can reach all dimensions. Do NOT write single-table queries.

**Single aggregate KPI with baseJoin (no trend/sparkline):**
```sql
SELECT COUNT(*) AS total_count
FROM orders o
LEFT JOIN payments p ON o.id = p.order_id
```
Mapping: `{"type": "kpi", "valueColumn": "total_count"}`

**KPI with autoTrend — simple last-2-rows comparison:**
```sql
SELECT o.month, SUM(o.revenue) AS revenue
FROM orders o
LEFT JOIN payments p ON o.id = p.order_id
GROUP BY o.month
ORDER BY o.month
```
Mapping: `{"type": "kpi", "valueColumn": "revenue", "aggregation": "last", "autoTrend": true, "periodLabel": "vs last period"}`
- Returns multiple rows → compares last 2 rows for trend
- `aggregation: "last"` uses the most recent row as the headline value

**KPI with autoTrend — date-based period comparison (recommended):**
```sql
SELECT o.order_date, o.revenue
FROM orders o
LEFT JOIN payments p ON o.id = p.order_id
ORDER BY o.order_date
```
Mapping: `{"type": "kpi", "valueColumn": "revenue", "aggregation": "sum", "autoTrend": true, "periodLabel": "vs last month", "trendDateColumn": "order_date"}`
- `trendDateColumn: "order_date"` tells the system which column holds dates
- `periodLabel: "vs last month"` → sums this month's rows vs last month's rows
- Headline value = this month's aggregate; trend % = change from last month

**KPI with legacy trend:**
```sql
SELECT
  current_value,
  pct_change,
  month,
  monthly_value
FROM summary_view
ORDER BY month
```
Mapping: `{"type": "kpi", "valueColumn": "current_value", "trendValueColumn": "pct_change", "sparklineXColumn": "month", "sparklineYColumn": "monthly_value"}`

### Best Practices

- **Always include trend context** — a bare number without trend lacks meaning
- **Prefer autoTrend over legacy** — simpler SQL, fewer mapping fields, less error-prone
- **Prefer date-based periods** — pair `periodLabel` with `trendDateColumn` for accurate comparisons; SQL should return individual rows (not pre-grouped) so the system can bucket them correctly
- For sparklines, SQL MUST return multiple rows ordered by time (not a single aggregate)
- Use `aggregation: "last"` for the most recent value in a time-series
- Use `aggregation: "sum"` for totals across all rows
- Position KPIs in the executive summary row: y=0, w=3 or w=4, h=2
"""
