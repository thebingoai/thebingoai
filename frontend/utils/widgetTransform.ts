export interface SqliteQueryResult {
  columns: string[]
  rows: any[][]
}

function toJsonSafe(value: any): any {
  // sql.js returns JS primitives already, no need for Decimal/datetime conversion
  return value
}

const DATE_BASED_PERIODS = new Set(['vs yesterday', 'vs last week', 'vs last month', 'vs last quarter', 'vs last year'])

function parseDate(value: any): Date | null {
  if (value instanceof Date) return value
  if (typeof value === 'string') {
    const d = new Date(value)
    return isNaN(d.getTime()) ? null : d
  }
  return null
}

function stripTime(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate())
}

const DOW_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/**
 * Bucket a raw label value by date granularity for time-series charts.
 * Returns [sortKey, display]. Mirrors backend widget_transform._bucket_label.
 * Falls back to [value, value] when not a parseable date or granularity is none.
 */
function bucketLabel(value: any, granularity?: string): [any, any] {
  if (!granularity || granularity === 'none') return [value, value]
  const dt = parseDate(value)
  if (!dt) return [value, value]
  const y = dt.getFullYear()
  const mo = dt.getMonth() + 1
  const pad = (n: number) => String(n).padStart(2, '0')
  switch (granularity) {
    case 'year': return [y, String(y)]
    case 'quarter': { const q = Math.floor((mo - 1) / 3) + 1; return [y * 10 + q, `${y}-Q${q}`] }
    case 'month': return [y * 100 + mo, `${y}-${pad(mo)}`]
    case 'week': {
      // ISO-ish week start (Monday) as the chronological key + display
      const dow = (dt.getDay() + 6) % 7 // 0 = Monday
      const start = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate() - dow)
      const key = start.getTime()
      return [key, `${start.getFullYear()}-${pad(start.getMonth() + 1)}-${pad(start.getDate())}`]
    }
    case 'day': return [new Date(y, dt.getMonth(), dt.getDate()).getTime(), `${y}-${pad(mo)}-${pad(dt.getDate())}`]
    case 'hour': return [new Date(y, dt.getMonth(), dt.getDate(), dt.getHours()).getTime(), `${y}-${pad(mo)}-${pad(dt.getDate())} ${pad(dt.getHours())}:00`]
    case 'hour_of_day': return [dt.getHours(), `${pad(dt.getHours())}:00`]
    case 'day_of_week': { const d = (dt.getDay() + 6) % 7; return [d, DOW_LABELS[d]] }
    case 'month_of_year': return [mo, MONTH_LABELS[mo - 1]]
    default: return [value, value]
  }
}

function periodRanges(periodLabel: string, ref: Date): [Date, Date, Date, Date] {
  const today = stripTime(ref)
  const y = today.getFullYear(), m = today.getMonth(), d = today.getDate()

  if (periodLabel === 'vs yesterday') {
    const yesterday = new Date(y, m, d - 1)
    return [today, today, yesterday, yesterday]
  }
  if (periodLabel === 'vs last week') {
    const dow = today.getDay() === 0 ? 6 : today.getDay() - 1 // Monday=0
    const curStart = new Date(y, m, d - dow)
    const curEnd = new Date(curStart.getFullYear(), curStart.getMonth(), curStart.getDate() + 6)
    const prevStart = new Date(curStart.getFullYear(), curStart.getMonth(), curStart.getDate() - 7)
    const prevEnd = new Date(curStart.getFullYear(), curStart.getMonth(), curStart.getDate() - 1)
    return [curStart, curEnd, prevStart, prevEnd]
  }
  if (periodLabel === 'vs last month') {
    const curStart = new Date(y, m, 1)
    const prevStart = new Date(y, m - 1, 1)
    const prevEnd = new Date(y, m, 0) // last day of prev month
    return [curStart, today, prevStart, prevEnd]
  }
  if (periodLabel === 'vs last quarter') {
    const q = Math.floor(m / 3)
    const curStart = new Date(y, q * 3, 1)
    const prevStart = new Date(y, (q - 1) * 3, 1)
    const prevEnd = new Date(curStart.getFullYear(), curStart.getMonth(), 0)
    return [curStart, today, prevStart, prevEnd]
  }
  if (periodLabel === 'vs last year') {
    const curStart = new Date(y, 0, 1)
    const prevStart = new Date(y - 1, 0, 1)
    const prevEnd = new Date(y, 0, 0)
    return [curStart, today, prevStart, prevEnd]
  }
  return [today, today, today, today]
}

function aggregateValues(values: any[], aggregation: string): number | null {
  if (!values.length) return null
  if (aggregation === 'count') return values.length
  if (aggregation === 'countDistinct') return new Set(values).size
  if (aggregation === 'first') return values[0]
  if (aggregation === 'last') return values[values.length - 1]
  const nums = values
    .map(v => {
      if (typeof v === 'number') return v
      if (typeof v === 'string' && v.trim() !== '') { const n = Number(v); return isNaN(n) ? NaN : n }
      return NaN
    })
    .filter(n => !isNaN(n))
  if (!nums.length) return null
  if (aggregation === 'sum') return nums.reduce((a, b) => a + b, 0)
  // Round avg to 2dp to match the backend transform (round(sum/len, 2)); display
  // layer may still reformat further via decimalPlaces / roundValues.
  if (aggregation === 'avg') return Math.round((nums.reduce((a, b) => a + b, 0) / nums.length) * 100) / 100
  if (aggregation === 'min') return Math.min(...nums)
  if (aggregation === 'max') return Math.max(...nums)
  return nums[0]
}

function dateInRange(d: Date, start: Date, end: Date): boolean {
  const t = stripTime(d).getTime()
  return t >= start.getTime() && t <= end.getTime()
}

function transformChart(result: SqliteQueryResult, mapping: Record<string, any>): Record<string, any> {
  const labelCol = mapping.labelColumn as string | undefined
  const datasetCols = (mapping.datasetColumns || []) as Array<{ column: string; label?: string; aggregation?: string; [key: string]: any }>
  const opts = (mapping.options ?? {}) as Record<string, any>

  const PASSTHROUGH_KEYS = new Set([
    'backgroundColor', 'borderColor', 'borderWidth', 'fill', 'tension', 'pointRadius',
    'seriesType', 'lineWeight', 'lineStyle', 'showPoints', 'stepped', 'gradient',
    'cumulative', 'showDataLabels', 'yAxisID', 'trendline',
  ])

  const empty = { data: { labels: [], datasets: [] } }

  // Ungrouped scatter/bubble series name — meaningful in tooltips ("y vs x").
  const xyLabel = mapping.xMetricColumn && mapping.yMetricColumn
    ? `${mapping.yMetricColumn} vs ${mapping.xMetricColumn}`
    : 'Scatter'

  // Guard: no rows → return empty structure with correct dataset labels
  if (!result.rows.length) {
    if (mapping.xMetricColumn && mapping.yMetricColumn) {
      return { data: { labels: [], datasets: [{ label: xyLabel, data: [] }] } }
    }
    return { data: { labels: [], datasets: datasetCols.map(ds => ({ label: ds.label || ds.column, data: [] })) } }
  }

  // ── SCATTER: x+y metric columns → {x, y} point objects ────────────────────
  // Optional: labelColumn groups points into one dataset (color) per value;
  // sizeMetricColumn adds `r` per point (bubble chart). Both raw-path only.
  if (mapping.xMetricColumn && mapping.yMetricColumn) {
    const xIdx = result.columns.indexOf(mapping.xMetricColumn as string)
    const yIdx = result.columns.indexOf(mapping.yMetricColumn as string)
    if (xIdx === -1 || yIdx === -1) return { data: { labels: [], datasets: [{ label: xyLabel, data: [] }] } }

    const yAgg = (mapping.yAggregation as string) || 'none'

    if (yAgg && yAgg !== 'none') {
      // Group by X, aggregate Y per group
      const order: any[] = []
      const groups = new Map<any, any[]>()
      for (const row of result.rows) {
        const xVal = toJsonSafe(row[xIdx])
        const yVal = toJsonSafe(row[yIdx])
        if (!groups.has(xVal)) { groups.set(xVal, []); order.push(xVal) }
        groups.get(xVal)!.push(yVal)
      }
      const points = order.map(x => ({ x, y: aggregateValues(groups.get(x)!, yAgg) ?? null }))
      return { data: { labels: [], datasets: [{ label: xyLabel, data: points }] } }
    }

    const sizeIdx = mapping.sizeMetricColumn ? result.columns.indexOf(mapping.sizeMetricColumn as string) : -1
    const toPoint = (row: any[]) => {
      const p: { x: any; y: any; r?: any } = { x: toJsonSafe(row[xIdx]), y: toJsonSafe(row[yIdx]) }
      if (sizeIdx !== -1) p.r = toJsonSafe(row[sizeIdx])
      return p
    }

    // Data Studio parity: max 1000 points per series — even downsample.
    const MAX_SCATTER_POINTS = 1000
    const cap = (pts: any[]) => {
      if (pts.length <= MAX_SCATTER_POINTS) return pts
      const step = Math.ceil(pts.length / MAX_SCATTER_POINTS)
      return pts.filter((_, i) => i % step === 0)
    }

    if (labelCol) {
      const groupIdx = result.columns.indexOf(labelCol)
      if (groupIdx !== -1) {
        const groups = new Map<string, any[]>()
        for (const row of result.rows) {
          const gk = String(toJsonSafe(row[groupIdx]))
          if (!groups.has(gk)) groups.set(gk, [])
          groups.get(gk)!.push(toPoint(row))
        }
        return { data: { labels: [], datasets: [...groups.entries()].map(([gk, pts]) => ({ label: gk, data: cap(pts) })) } }
      }
    }

    return { data: { labels: [], datasets: [{ label: xyLabel, data: cap(result.rows.map(toPoint)) }] } }
  }

  // ── STANDARD: dimension + metric columns ──────────────────────────────────
  if (!labelCol) return empty
  const labelIdx = result.columns.indexOf(labelCol)
  if (labelIdx === -1) return empty
  if (!datasetCols.length) return { data: { labels: [], datasets: [] } }

  const hasAggregation = datasetCols.some(ds => ds.aggregation && ds.aggregation !== 'none')
  const missingData = opts.missingData as string | undefined
  const granularity = mapping.dateGranularity as string | undefined
  const hasGranularity = !!(granularity && granularity !== 'none')
  const breakdownCol = mapping.breakdownColumn as string | undefined

  const bucket = (v: any): [any, any] => hasGranularity ? bucketLabel(toJsonSafe(v), granularity) : [toJsonSafe(v), toJsonSafe(v)]

  let labels: any[]
  let datasets: any[]

  if (breakdownCol) {
    // Series breakdown: pivot the FIRST metric into one dataset per distinct
    // breakdown value (mirrors backend transform_chart breakdown block).
    const breakdownIdx = result.columns.indexOf(breakdownCol)
    if (breakdownIdx === -1) throw new Error(`Column '${breakdownCol}' not found in query results`)
    const measure = datasetCols[0]
    const mIdx = result.columns.indexOf(measure.column)
    if (mIdx === -1) throw new Error(`Column '${measure.column}' not found in query results`)
    let agg = measure.aggregation || 'sum'
    if (agg === 'none') agg = 'sum'

    const labelKeys = new Map<any, any>()
    labels = []
    const seriesSeq: any[] = []
    const seriesSeen = new Set<any>()
    const cells = new Map<string, any[]>()
    for (const row of result.rows) {
      const [sk, disp] = bucket(row[labelIdx])
      if (!labelKeys.has(disp)) { labelKeys.set(disp, sk); labels.push(disp) }
      const bv = toJsonSafe(row[breakdownIdx])
      if (!seriesSeen.has(bv)) { seriesSeen.add(bv); seriesSeq.push(bv) }
      const ck = `${disp} ${bv}`
      if (!cells.has(ck)) cells.set(ck, [])
      cells.get(ck)!.push(toJsonSafe(row[mIdx]))
    }
    if (hasGranularity) labels.sort((a, b) => (labelKeys.get(a) > labelKeys.get(b) ? 1 : labelKeys.get(a) < labelKeys.get(b) ? -1 : 0))

    datasets = seriesSeq.map(bv => {
      let data: any[] = labels.map(d => {
        const vals = cells.get(`${d} ${bv}`) ?? []
        return vals.length ? (aggregateValues(vals, agg) ?? null) : null
      })
      if (missingData === 'lineToZero') data = data.map((v: any) => v == null ? 0 : v)
      return { label: bv == null ? '(null)' : String(bv), data }
    })
  } else if (hasAggregation || hasGranularity) {
    // Group rows by (bucketed) labelColumn, aggregate per group
    const labelOrder: any[] = []
    const labelKeys = new Map<any, any>()
    const groups = new Map<any, any[][]>()
    for (const row of result.rows) {
      const [sk, lv] = bucket(row[labelIdx])
      if (!groups.has(lv)) { groups.set(lv, []); labelOrder.push(lv); labelKeys.set(lv, sk) }
      groups.get(lv)!.push(row)
    }
    if (hasGranularity) labelOrder.sort((a, b) => (labelKeys.get(a) > labelKeys.get(b) ? 1 : labelKeys.get(a) < labelKeys.get(b) ? -1 : 0))
    labels = labelOrder

    datasets = datasetCols.map(ds => {
      const colIdx = result.columns.indexOf(ds.column)
      if (colIdx === -1) throw new Error(`Column '${ds.column}' not found in query results`)
      let agg = ds.aggregation || 'sum'
      if (agg === 'none' && hasGranularity) agg = 'sum'
      let data: any[] = labels.map(lv => {
        const rows = groups.get(lv) ?? []
        const vals = rows.map(row => toJsonSafe(row[colIdx]))
        return agg === 'none' ? (vals[0] ?? null) : (aggregateValues(vals, agg) ?? null)
      })
      if (missingData === 'lineToZero') data = data.map((v: any) => v == null ? 0 : v)
      const dataset: Record<string, any> = { label: ds.label || ds.column, data }
      for (const key of PASSTHROUGH_KEYS) { if (key in ds) dataset[key] = ds[key] }
      if (ds.cumulative) {
        let running = 0
        dataset.data = dataset.data.map((v: any) => { running += (typeof v === 'number' ? v : 0); return running })
      }
      return dataset
    })
  } else {
    // Original 1:1 row mapping
    labels = result.rows.map(row => toJsonSafe(row[labelIdx]))
    datasets = datasetCols.map(ds => {
      const colIdx = result.columns.indexOf(ds.column)
      if (colIdx === -1) throw new Error(`Column '${ds.column}' not found in query results`)
      const rawData = result.rows.map(row => toJsonSafe(row[colIdx]))
      const data = missingData === 'lineToZero' ? rawData.map((v: any) => (v == null ? 0 : v)) : rawData
      const dataset: Record<string, any> = { label: ds.label || ds.column, data }
      for (const key of PASSTHROUGH_KEYS) { if (key in ds) dataset[key] = ds[key] }
      if (ds.cumulative) {
        let running = 0
        dataset.data = dataset.data.map((v: any) => { running += (typeof v === 'number' ? v : 0); return running })
      }
      return dataset
    })
  }

  // Limit to last N points (after aggregation, before percentage)
  const numberOfPoints = opts.numberOfPoints as number | undefined
  if (numberOfPoints && numberOfPoints > 0 && datasets.length > 0) {
    labels = labels.slice(-numberOfPoints)
    datasets = datasets.map(ds => ({ ...ds, data: ds.data.slice(-numberOfPoints) }))
  }

  // 100% stacked normalization
  if (opts.stacked === 'percentage') {
    for (let i = 0; i < labels.length; i++) {
      const total = datasets.reduce((sum: number, ds: any) => {
        const v = ds.data[i]
        return sum + (typeof v === 'number' ? v : 0)
      }, 0)
      if (total > 0) {
        for (const ds of datasets) {
          const v = ds.data[i]
          ds.data[i] = typeof v === 'number' ? Math.round((v / total) * 10000) / 100 : 0
        }
      }
    }
  }

  return { data: { labels, datasets } }
}

function transformKpi(result: SqliteQueryResult, mapping: Record<string, any>): Record<string, any> {
  const valueCol = mapping.valueColumn as string
  const trendCol = mapping.trendValueColumn as string | undefined
  const sparklineXCol = mapping.sparklineXColumn as string | undefined
  const sparklineYCol = mapping.sparklineYColumn as string | undefined

  const valueIdx = result.columns.indexOf(valueCol)
  if (valueIdx === -1) throw new Error(`Column '${valueCol}' not found in query results`)
  if (!result.rows.length) throw new Error('Query returned no rows — cannot build KPI widget')

  const firstRow = result.rows[0]
  // Mirror transform_kpi: an absent aggregation on a multi-row result means
  // sum, not row 0. Single-row results are identical either way.
  const aggregation = (mapping.aggregation as string) ?? (result.rows.length > 1 ? 'sum' : 'first')
  const allColValues = result.rows.map(row => toJsonSafe(row[valueIdx])).filter(v => v != null)
  const value = aggregation === 'first'
    ? toJsonSafe(firstRow[valueIdx])
    : aggregateValues(allColValues, aggregation)
  const config: Record<string, any> = { value }

  const autoTrend = mapping.autoTrend as boolean | undefined
  const periodLabel = (mapping.periodLabel as string) ?? ''

  // Auto-trend: derive trend + sparkline from multi-row time-series results
  if (autoTrend) {
    const allValues = result.rows
      .map(row => toJsonSafe(row[valueIdx]))
      .filter((v): v is number => typeof v === 'number')

    if (allValues.length > 0) {
      config.sparkline = allValues
      config.value = allValues[allValues.length - 1]
    }

    const dateCol = mapping.trendDateColumn as string | undefined
    const dateIdx = dateCol ? result.columns.indexOf(dateCol) : -1

    // Period-based comparison using date column
    if (dateCol && dateIdx !== -1 && DATE_BASED_PERIODS.has(periodLabel)) {
      const [curStart, curEnd, prevStart, prevEnd] = periodRanges(periodLabel, new Date())
      const curValues: number[] = []
      const prevValues: number[] = []

      for (const row of result.rows) {
        const v = toJsonSafe(row[valueIdx])
        if (typeof v !== 'number') continue
        const d = parseDate(row[dateIdx])
        if (!d) continue
        if (dateInRange(d, curStart, curEnd)) curValues.push(v)
        else if (dateInRange(d, prevStart, prevEnd)) prevValues.push(v)
      }

      const curAgg = aggregateValues(curValues, aggregation)
      const prevAgg = aggregateValues(prevValues, aggregation)

      if (curAgg !== null) config.value = curAgg

      if (curAgg !== null && prevAgg !== null && prevAgg !== 0) {
        const trendPct = Math.round(((curAgg - prevAgg) / Math.abs(prevAgg)) * 10000) / 100
        const direction = trendPct > 0 ? 'up' : trendPct < 0 ? 'down' : 'neutral'
        config.trend = { direction, value: trendPct, period: periodLabel }
      } else if (curAgg !== null && prevAgg !== null) {
        config.trend = { direction: 'neutral', value: 0, period: periodLabel }
      }

    // Fallback: simple last-two-rows comparison
    } else if (allValues.length >= 2) {
      const current = allValues[allValues.length - 1]
      const previous = allValues[allValues.length - 2]
      if (previous !== 0) {
        const trendPct = Math.round(((current - previous) / Math.abs(previous)) * 10000) / 100
        const direction = trendPct > 0 ? 'up' : trendPct < 0 ? 'down' : 'neutral'
        config.trend = { direction, value: trendPct, period: periodLabel }
      } else {
        config.trend = { direction: 'neutral', value: 0, period: periodLabel }
      }
    }
    // autoTrend with < 2 numeric values and no date-based period: no trend emitted
  } else if (trendCol) {
    const trendIdx = result.columns.indexOf(trendCol)
    if (trendIdx !== -1) {
      const trendVal = toJsonSafe(firstRow[trendIdx])
      const direction = typeof trendVal === 'number' && trendVal > 0 ? 'up' : typeof trendVal === 'number' && trendVal < 0 ? 'down' : 'neutral'
      config.trend = { direction, value: trendVal }
    }
  }

  if (sparklineYCol) {
    const sortCol = mapping.sparklineSortColumn as string | undefined
    const sortDir = (mapping.sparklineSortDirection as string) ?? 'asc'
    let rows = result.rows
    if (sortCol) {
      const sortIdx = result.columns.indexOf(sortCol)
      if (sortIdx !== -1) {
        const mul = sortDir === 'desc' ? -1 : 1
        rows = [...rows].sort((a, b) => {
          const va = a[sortIdx], vb = b[sortIdx]
          if (va == null && vb == null) return 0
          if (va == null) return -mul
          if (vb == null) return mul
          return va < vb ? -mul : va > vb ? mul : 0
        })
      }
    }
    const sparkYIdx = result.columns.indexOf(sparklineYCol)
    if (sparkYIdx !== -1) {
      config.sparkline = rows.map(row => toJsonSafe(row[sparkYIdx]))
    }
    if (sparklineXCol) {
      const sparkXIdx = result.columns.indexOf(sparklineXCol)
      if (sparkXIdx !== -1) {
        config.sparklineLabels = rows.map(row => String(toJsonSafe(row[sparkXIdx])))
      }
    }
  }

  return config
}

function transformTable(result: SqliteQueryResult, mapping: Record<string, any>): Record<string, any> {
  const colConfig = (mapping.columnConfig || []) as Array<{ column: string; label?: string; sortable?: boolean; format?: string }>

  const columns = colConfig.map(cc => {
    const colDef: Record<string, any> = { key: cc.column, label: cc.label || cc.column }
    if ('sortable' in cc) colDef.sortable = cc.sortable
    if ('format' in cc) colDef.format = cc.format
    return colDef
  })

  const rows = result.rows.map(row => {
    const rowDict: Record<string, any> = {}
    for (const cc of colConfig) {
      const colIdx = result.columns.indexOf(cc.column)
      rowDict[cc.column] = colIdx !== -1 ? toJsonSafe(row[colIdx]) : null
    }
    return rowDict
  })

  return { columns, rows }
}

// Pivot table — passthrough (same shape as table). The pivot grouping/aggregation
// is computed client-side in DashboardWidgetPivotTable.vue from config + rows.
function transformPivotTable(result: SqliteQueryResult, mapping: Record<string, any>): Record<string, any> {
  return transformTable(result, mapping)
}

export function transformWidgetData(result: SqliteQueryResult, mapping: Record<string, any>): Record<string, any> {
  const mappingType = mapping.type
  if (mappingType === 'chart') return transformChart(result, mapping)
  if (mappingType === 'kpi') return transformKpi(result, mapping)
  if (mappingType === 'table') return transformTable(result, mapping)
  if (mappingType === 'pivot_table') return transformPivotTable(result, mapping)
  throw new Error(`Unsupported mapping type: '${mappingType}'. Must be one of: chart, kpi, table, pivot_table`)
}
