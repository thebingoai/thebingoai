import { describe, it, expect } from 'vitest'
import { transformWidgetData, type SqliteQueryResult } from '~/utils/widgetTransform'

// ---------------------------------------------------------------------------
// Helpers to build test fixtures
// ---------------------------------------------------------------------------
function makeResult(columns: string[], rows: any[][]): SqliteQueryResult {
  return { columns, rows }
}

// ---------------------------------------------------------------------------
// Chart transform
// ---------------------------------------------------------------------------
describe('transformWidgetData — chart', () => {
  const chartResult = makeResult(
    ['month', 'revenue', 'cost'],
    [
      ['Jan', 100, 50],
      ['Feb', 200, 80],
      ['Mar', 150, 60],
    ],
  )

  it('extracts labels from the labelColumn', () => {
    const mapping = {
      type: 'chart',
      labelColumn: 'month',
      datasetColumns: [{ column: 'revenue' }],
    }
    const out = transformWidgetData(chartResult, mapping)
    expect(out.data.labels).toEqual(['Jan', 'Feb', 'Mar'])
  })

  it('extracts dataset data from the correct column', () => {
    const mapping = {
      type: 'chart',
      labelColumn: 'month',
      datasetColumns: [{ column: 'revenue', label: 'Revenue' }],
    }
    const out = transformWidgetData(chartResult, mapping)
    expect(out.data.datasets[0].data).toEqual([100, 200, 150])
    expect(out.data.datasets[0].label).toBe('Revenue')
  })

  it('preserves passthrough keys (backgroundColor, borderColor, etc.)', () => {
    const mapping = {
      type: 'chart',
      labelColumn: 'month',
      datasetColumns: [
        {
          column: 'revenue',
          backgroundColor: '#ff0000',
          borderColor: '#00ff00',
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointRadius: 3,
        },
      ],
    }
    const out = transformWidgetData(chartResult, mapping)
    const ds = out.data.datasets[0]
    expect(ds.backgroundColor).toBe('#ff0000')
    expect(ds.borderColor).toBe('#00ff00')
    expect(ds.borderWidth).toBe(2)
    expect(ds.fill).toBe(true)
    expect(ds.tension).toBe(0.4)
    expect(ds.pointRadius).toBe(3)
  })

  it('throws when the label column is missing', () => {
    const mapping = {
      type: 'chart',
      labelColumn: 'nonexistent',
      datasetColumns: [{ column: 'revenue' }],
    }
    expect(() => transformWidgetData(chartResult, mapping)).toThrowError(
      "Column 'nonexistent' not found",
    )
  })

  it('throws when a dataset column is missing', () => {
    const mapping = {
      type: 'chart',
      labelColumn: 'month',
      datasetColumns: [{ column: 'profit' }],
    }
    expect(() => transformWidgetData(chartResult, mapping)).toThrowError(
      "Column 'profit' not found",
    )
  })
})

// ---------------------------------------------------------------------------
// KPI transform
// ---------------------------------------------------------------------------
describe('transformWidgetData — kpi', () => {
  it('extracts a basic value from the first row', () => {
    const result = makeResult(['total'], [[42]])
    const mapping = { type: 'kpi', valueColumn: 'total' }
    const out = transformWidgetData(result, mapping)
    expect(out.value).toBe(42)
  })

  it('computes autoTrend with 2+ rows (last-two-rows fallback)', () => {
    const result = makeResult(['sales'], [[80], [100]])
    const mapping = { type: 'kpi', valueColumn: 'sales', autoTrend: true }
    const out = transformWidgetData(result, mapping)
    // current = 100, previous = 80 => (100-80)/80 * 100 = 25%
    expect(out.trend.direction).toBe('up')
    expect(out.trend.value).toBe(25)
    expect(out.value).toBe(100) // autoTrend overrides value to last
  })

  it('autoTrend with current > previous yields "up" direction', () => {
    const result = makeResult(['v'], [[10], [20]])
    const mapping = { type: 'kpi', valueColumn: 'v', autoTrend: true }
    const out = transformWidgetData(result, mapping)
    expect(out.trend.direction).toBe('up')
  })

  it('autoTrend produces sparkline from all numeric values', () => {
    const result = makeResult(['v'], [[10], [20], [30]])
    const mapping = { type: 'kpi', valueColumn: 'v', autoTrend: true }
    const out = transformWidgetData(result, mapping)
    expect(out.sparkline).toEqual([10, 20, 30])
  })

  it('autoTrend with zero previous value yields neutral trend', () => {
    const result = makeResult(['v'], [[0], [50]])
    const mapping = { type: 'kpi', valueColumn: 'v', autoTrend: true }
    const out = transformWidgetData(result, mapping)
    expect(out.trend.direction).toBe('neutral')
    expect(out.trend.value).toBe(0)
  })

  it('autoTrend with a single row produces no trend', () => {
    const result = makeResult(['v'], [[99]])
    const mapping = { type: 'kpi', valueColumn: 'v', autoTrend: true }
    const out = transformWidgetData(result, mapping)
    expect(out.trend).toBeUndefined()
    expect(out.value).toBe(99)
  })

  it('explicit trendCol (not autoTrend) extracts trend direction', () => {
    const result = makeResult(['v', 'change'], [[500, -3]])
    const mapping = { type: 'kpi', valueColumn: 'v', trendValueColumn: 'change' }
    const out = transformWidgetData(result, mapping)
    expect(out.trend.direction).toBe('down')
    expect(out.trend.value).toBe(-3)
  })

  it('throws when value column is missing', () => {
    const result = makeResult(['x'], [[1]])
    const mapping = { type: 'kpi', valueColumn: 'missing' }
    expect(() => transformWidgetData(result, mapping)).toThrowError(
      "Column 'missing' not found",
    )
  })

  it('throws when rows are empty', () => {
    const result = makeResult(['v'], [])
    const mapping = { type: 'kpi', valueColumn: 'v' }
    expect(() => transformWidgetData(result, mapping)).toThrowError(
      'Query returned no rows',
    )
  })
})

// ---------------------------------------------------------------------------
// Table transform
// ---------------------------------------------------------------------------
describe('transformWidgetData — table', () => {
  const tableResult = makeResult(
    ['id', 'name', 'email'],
    [
      [1, 'Alice', 'alice@test.com'],
      [2, 'Bob', 'bob@test.com'],
    ],
  )

  it('maps columns with key and label', () => {
    const mapping = {
      type: 'table',
      columnConfig: [
        { column: 'id', label: 'ID' },
        { column: 'name', label: 'Name' },
      ],
    }
    const out = transformWidgetData(tableResult, mapping)
    expect(out.columns[0]).toEqual({ key: 'id', label: 'ID' })
    expect(out.columns[1]).toEqual({ key: 'name', label: 'Name' })
  })

  it('converts rows to dictionaries keyed by column', () => {
    const mapping = {
      type: 'table',
      columnConfig: [
        { column: 'id', label: 'ID' },
        { column: 'name', label: 'Name' },
      ],
    }
    const out = transformWidgetData(tableResult, mapping)
    expect(out.rows[0]).toEqual({ id: 1, name: 'Alice' })
    expect(out.rows[1]).toEqual({ id: 2, name: 'Bob' })
  })

  it('returns null for a missing column in a row', () => {
    const mapping = {
      type: 'table',
      columnConfig: [{ column: 'nonexistent', label: 'Missing' }],
    }
    const out = transformWidgetData(tableResult, mapping)
    expect(out.rows[0].nonexistent).toBeNull()
  })

  it('preserves sortable and format config', () => {
    const mapping = {
      type: 'table',
      columnConfig: [
        { column: 'id', label: 'ID', sortable: true, format: 'number' },
      ],
    }
    const out = transformWidgetData(tableResult, mapping)
    expect(out.columns[0].sortable).toBe(true)
    expect(out.columns[0].format).toBe('number')
  })
})

// ---------------------------------------------------------------------------
// aggregateValues (tested indirectly through autoTrend with period-based KPI)
// We test the various aggregation modes via the public API.
// ---------------------------------------------------------------------------
describe('transformWidgetData — aggregateValues (via period-based KPI)', () => {
  // Build a dataset where we can control the date ranges to exercise aggregateValues.
  // For 'vs yesterday': curStart=today, curEnd=today, prevStart=yesterday, prevEnd=yesterday

  function todayStr(): string {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }

  function yesterdayStr(): string {
    const d = new Date()
    d.setDate(d.getDate() - 1)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }

  it('sum aggregation computes correct current value', () => {
    const result = makeResult(
      ['dt', 'v'],
      [
        [todayStr(), 10],
        [todayStr(), 20],
        [yesterdayStr(), 5],
      ],
    )
    const mapping = {
      type: 'kpi',
      valueColumn: 'v',
      autoTrend: true,
      trendDateColumn: 'dt',
      periodLabel: 'vs yesterday',
      aggregation: 'sum',
    }
    const out = transformWidgetData(result, mapping)
    // sum of today values = 30, sum of yesterday = 5
    expect(out.value).toBe(30)
  })

  it('avg aggregation computes correct current value', () => {
    const result = makeResult(
      ['dt', 'v'],
      [
        [todayStr(), 10],
        [todayStr(), 20],
        [yesterdayStr(), 5],
      ],
    )
    const mapping = {
      type: 'kpi',
      valueColumn: 'v',
      autoTrend: true,
      trendDateColumn: 'dt',
      periodLabel: 'vs yesterday',
      aggregation: 'avg',
    }
    const out = transformWidgetData(result, mapping)
    // avg of today values = (10+20)/2 = 15
    expect(out.value).toBe(15)
  })

  it('count aggregation returns number of values', () => {
    const result = makeResult(
      ['dt', 'v'],
      [
        [todayStr(), 10],
        [todayStr(), 20],
        [yesterdayStr(), 5],
      ],
    )
    const mapping = {
      type: 'kpi',
      valueColumn: 'v',
      autoTrend: true,
      trendDateColumn: 'dt',
      periodLabel: 'vs yesterday',
      aggregation: 'count',
    }
    const out = transformWidgetData(result, mapping)
    // count of today values = 2
    expect(out.value).toBe(2)
  })

  it('min aggregation returns smallest value', () => {
    const result = makeResult(
      ['dt', 'v'],
      [
        [todayStr(), 10],
        [todayStr(), 20],
        [yesterdayStr(), 5],
      ],
    )
    const mapping = {
      type: 'kpi',
      valueColumn: 'v',
      autoTrend: true,
      trendDateColumn: 'dt',
      periodLabel: 'vs yesterday',
      aggregation: 'min',
    }
    const out = transformWidgetData(result, mapping)
    expect(out.value).toBe(10)
  })

  it('max aggregation returns largest value', () => {
    const result = makeResult(
      ['dt', 'v'],
      [
        [todayStr(), 10],
        [todayStr(), 20],
        [yesterdayStr(), 5],
      ],
    )
    const mapping = {
      type: 'kpi',
      valueColumn: 'v',
      autoTrend: true,
      trendDateColumn: 'dt',
      periodLabel: 'vs yesterday',
      aggregation: 'max',
    }
    const out = transformWidgetData(result, mapping)
    expect(out.value).toBe(20)
  })

  it('last aggregation returns last value in period', () => {
    const result = makeResult(
      ['dt', 'v'],
      [
        [todayStr(), 10],
        [todayStr(), 20],
        [yesterdayStr(), 5],
      ],
    )
    const mapping = {
      type: 'kpi',
      valueColumn: 'v',
      autoTrend: true,
      trendDateColumn: 'dt',
      periodLabel: 'vs yesterday',
      aggregation: 'last',
    }
    const out = transformWidgetData(result, mapping)
    // last of today values = 20 (last in array order)
    expect(out.value).toBe(20)
  })

  it('first aggregation returns first value in period', () => {
    const result = makeResult(
      ['dt', 'v'],
      [
        [todayStr(), 10],
        [todayStr(), 20],
        [yesterdayStr(), 5],
      ],
    )
    const mapping = {
      type: 'kpi',
      valueColumn: 'v',
      autoTrend: true,
      trendDateColumn: 'dt',
      periodLabel: 'vs yesterday',
      aggregation: 'first',
    }
    const out = transformWidgetData(result, mapping)
    // 'first' is the default fallback in aggregateValues => values[0] = 10
    expect(out.value).toBe(10)
  })
})

// ---------------------------------------------------------------------------
// Dispatch tests
// ---------------------------------------------------------------------------
describe('transformWidgetData — dispatch', () => {
  const simpleResult = makeResult(['x'], [[1]])

  it("type 'chart' routes to chart transform", () => {
    const mapping = {
      type: 'chart',
      labelColumn: 'x',
      datasetColumns: [{ column: 'x' }],
    }
    const out = transformWidgetData(simpleResult, mapping)
    expect(out).toHaveProperty('data.labels')
    expect(out).toHaveProperty('data.datasets')
  })

  it("type 'kpi' routes to kpi transform", () => {
    const mapping = { type: 'kpi', valueColumn: 'x' }
    const out = transformWidgetData(simpleResult, mapping)
    expect(out).toHaveProperty('value')
  })

  it("type 'table' routes to table transform", () => {
    const mapping = {
      type: 'table',
      columnConfig: [{ column: 'x', label: 'X' }],
    }
    const out = transformWidgetData(simpleResult, mapping)
    expect(out).toHaveProperty('columns')
    expect(out).toHaveProperty('rows')
  })

  it('unknown type throws Error with message listing valid types', () => {
    const mapping = { type: 'pie' }
    expect(() => transformWidgetData(simpleResult, mapping)).toThrowError(
      /Must be one of: chart, kpi, table/,
    )
  })
})
