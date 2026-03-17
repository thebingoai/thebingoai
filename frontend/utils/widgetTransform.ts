export interface SqliteQueryResult {
  columns: string[]
  rows: any[][]
}

function toJsonSafe(value: any): any {
  // sql.js returns JS primitives already, no need for Decimal/datetime conversion
  return value
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
  const sparklineCol = mapping.sparklineColumn as string | undefined

  const valueIdx = result.columns.indexOf(valueCol)
  if (valueIdx === -1) throw new Error(`Column '${valueCol}' not found in query results`)
  if (!result.rows.length) throw new Error('Query returned no rows — cannot build KPI widget')

  const firstRow = result.rows[0]
  const value = toJsonSafe(firstRow[valueIdx])
  const config: Record<string, any> = { value }

  if (trendCol) {
    const trendIdx = result.columns.indexOf(trendCol)
    if (trendIdx !== -1) {
      const trendVal = toJsonSafe(firstRow[trendIdx])
      const direction = typeof trendVal === 'number' && trendVal > 0 ? 'up' : typeof trendVal === 'number' && trendVal < 0 ? 'down' : 'neutral'
      config.trend = { direction, value: trendVal }
    }
  }

  if (sparklineCol) {
    const sparkIdx = result.columns.indexOf(sparklineCol)
    if (sparkIdx !== -1) {
      config.sparkline = result.rows.map(row => toJsonSafe(row[sparkIdx]))
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
