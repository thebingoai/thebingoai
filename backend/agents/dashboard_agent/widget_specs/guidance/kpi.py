"""Hand-written guidance for the KPI widget type."""

KPI_GUIDANCE = """### autoTrend vs Legacy Trend

**autoTrend: true (recommended):** SQL returns multiple time-ordered rows. The system automatically:
- Computes the headline value using the `aggregation` method — always set it explicitly to match the KPI's purpose (sum, avg, countDistinct, last, ...). If omitted, a multi-row result is summed, and raw-row SQL without it is rejected before save.
- Derives trend direction and % change

**Trend calculation is controlled by `periodLabel`:**
- `"vs last period"` (or omitted) — compares the last 2 rows in query order (simplest)
- `"vs yesterday"` / `"vs last week"` / `"vs last month"` / `"vs last quarter"` / `"vs last year"` — **date-based**: buckets rows into current and previous period using `trendDateColumn`, aggregates each bucket with the KPI's `aggregation` method, and computes trend % from the two aggregated values. **Requires `trendDateColumn`.**

**Legacy (use only when you need full control):** Manually specify separate columns:
- `trendValueColumn` — a pre-computed trend number in the SQL output

### SQL Patterns (use baseJoin from data context)

IMPORTANT: Every KPI must include the baseJoin from the dashboard data context so that
dashboard filters can reach all dimensions. Do NOT write single-table queries.

**Single aggregate KPI with baseJoin (no trend):**
```sql
SELECT COUNT(*) AS total_count
FROM orders o
LEFT JOIN payments p ON o.id = p.order_id
```
Mapping: `{"type": "kpi", "valueColumn": "total_count", "aggregation": "sum"}`

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
  pct_change
FROM summary_view
```
Mapping: `{"type": "kpi", "valueColumn": "current_value", "aggregation": "first", "trendValueColumn": "pct_change"}`
- The SQL returns a single pre-computed row, so `aggregation: "first"` states that intent explicitly. Every KPI needs either an aggregating SQL (GROUP BY / SUM / COUNT) or an explicit `aggregation` — omitting both is rejected before the dashboard is saved.

### Best Practices

- **Always include trend context** — a bare number without trend lacks meaning
- **Cast text numerics inside aggregates** — if the profiled column type is TEXT/STRING, use `AVG(SAFE_CAST(col AS FLOAT64))`; `AVG(STRING)` fails on BigQuery
- **Prefer autoTrend over legacy** — simpler SQL, fewer mapping fields, less error-prone
- **Prefer date-based periods** — pair `periodLabel` with `trendDateColumn` for accurate comparisons; SQL should return individual rows (not pre-grouped) so the system can bucket them correctly
- **Bound date-based queries** — only the current + previous period matter, so add a WHERE on the date column (e.g. last 60 days for "vs last month") instead of scanning full history
- Use `aggregation: "last"` for the most recent value in a time-series
- Use `aggregation: "sum"` for totals across all rows
- KPIs live ONLY in the executive summary band directly below the filter bar — the backend packs the row; never emit a KPI inside a later section
- Mix the band: headline level(s) with `autoTrend`, plus a target-progress KPI when a goal exists — not five identical counts
- Set `compactNumbers: true` whenever the value can exceed ~10,000 (renders 1.2M instead of 1,200,000)
- When the user mentions a goal/target/quota, render it as progress:
  `"comparison": {"type": "value", "targetValue": <goal>, "showAsProgress": true}` plus `"progressVisual": "bar"` in config
"""
