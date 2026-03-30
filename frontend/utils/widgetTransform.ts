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

function aggregateValues(values: number[], aggregation: string): number | null {
  if (!values.length) return null
  if (aggregation === 'sum') return values.reduce((a, b) => a + b, 0)
  if (aggregation === 'avg') return Math.round((values.reduce((a, b) => a + b, 0) / values.length) * 100) / 100
  if (aggregation === 'count') return values.length
  if (aggregation === 'min') return Math.min(...values)
  if (aggregation === 'max') return Math.max(...values)
  if (aggregation === 'last') return values[values.length - 1]
  return values[0] // 'first'
}

function dateInRange(d: Date, start: Date, end: Date): boolean {
  const t = stripTime(d).getTime()
  return t >= start.getTime() && t <= end.getTime()
}

function transformChart(result: SqliteQueryResult, mapping: Record<string, any>): Record<string, any> {
  const labelCol = mapping.labelColumn as string
  const datasetCols = (mapping.datasetColumns || []) as Array<{ column: string; label?: string; [key: string]: any }>

  const labelIdx = result.columns.indexOf(labelCol)
  if (labelIdx === -1) throw new Error(`Column '${labelCol}' not found in query results`)

  const labels = result.rows.map(row => toJsonSafe(row[labelIdx]))

  const PASSTHROUGH_KEYS = new Set(['backgroundColor', 'borderColor', 'borderWidth', 'fill', 'tension', 'pointRadius'])

  const datasets = datasetCols.map(ds => {
    const colIdx = result.columns.indexOf(ds.column)
    if (colIdx === -1) throw new Error(`Column '${ds.column}' not found in query results`)
    const dataset: Record<string, any> = {
      label: ds.label || ds.column,
      data: result.rows.map(row => toJsonSafe(row[colIdx])),
    }
    for (const key of PASSTHROUGH_KEYS) {
      if (key in ds) dataset[key] = ds[key]
    }
    return dataset
  })

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
  const value = toJsonSafe(firstRow[valueIdx])
  const config: Record<string, any> = { value }

  const autoTrend = mapping.autoTrend as boolean | undefined
  const periodLabel = (mapping.periodLabel as string) ?? ''

  const aggregation = (mapping.aggregation as string) ?? 'first'

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

export function transformWidgetData(result: SqliteQueryResult, mapping: Record<string, any>): Record<string, any> {
  const mappingType = mapping.type
  if (mappingType === 'chart') return transformChart(result, mapping)
  if (mappingType === 'kpi') return transformKpi(result, mapping)
  if (mappingType === 'table') return transformTable(result, mapping)
  throw new Error(`Unsupported mapping type: '${mappingType}'. Must be one of: chart, kpi, table`)
}
