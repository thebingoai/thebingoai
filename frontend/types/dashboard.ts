import type { ChartConfig, ChartType } from './chart'

export type WidgetType = 'kpi' | 'chart' | 'table' | 'text' | 'filter'

// 12-column grid position
export interface GridPosition {
  x: number
  y: number
  w: number
  h: number
  minW?: number
  minH?: number
  maxW?: number
  maxH?: number
}

// KPI scorecard widget
export interface KpiWidgetConfig {
  value: number | string
  label: string
  prefix?: string
  suffix?: string
  trend?: {
    direction: 'up' | 'down' | 'neutral'
    value: number
    period?: string
  }
  sparkline?: number[]
  sparklineLabels?: string[]
}

// Chart widget — alias for existing ChartConfig (zero migration cost)
export type ChartWidgetConfig = ChartConfig

// Table widget
export interface TableColumn {
  key: string
  label: string
  sortable?: boolean
  filterable?: boolean
  format?: 'number' | 'currency' | 'percent' | 'date' | 'text'
}

export interface TableWidgetConfig {
  columns: TableColumn[]
  rows: Record<string, any>[]
  pagination?: boolean
  rowsPerPage?: number
}

// Text/markdown widget
export interface TextWidgetConfig {
  content: string
  alignment?: 'left' | 'center' | 'right'
}

// Filter widget
export interface FilterOptionsSource {
  connectionId: number
  sql: string  // e.g. "SELECT DISTINCT col AS option_value FROM table ORDER BY 1 LIMIT 50"
}

export interface FilterControl {
  type: 'date_range' | 'dropdown' | 'search'
  label: string
  key: string
  column?: string                    // real DB column name (used for SQL filtering)
  dimension?: string                 // references data_context.dimensions key
  multiple?: boolean                 // allow multi-select (dropdown only)
  options?: string[]                 // static fallback options
  optionsSource?: FilterOptionsSource // dynamic SQL-based options
}

export interface FilterWidgetConfig {
  controls: FilterControl[]
}

// DataSource mapping types — one per refreshable widget type
export interface ChartDataSourceMapping {
  type: 'chart'
  labelColumn: string
  datasetColumns: { column: string; label: string }[]
}

export interface KpiDataSourceMapping {
  type: 'kpi'
  valueColumn: string
  aggregation?: 'sum' | 'avg' | 'count' | 'min' | 'max' | 'first' | 'last'
  // Auto-trend: derive trend + sparkline from multi-row time-series results
  autoTrend?: boolean
  periodLabel?: string          // display label e.g. "vs last month"
  // Legacy: pre-computed trend (kept for backward compat)
  trendValueColumn?: string
  sparklineXColumn?: string
  sparklineYColumn?: string
  sparklineSortColumn?: string
  sparklineSortDirection?: 'asc' | 'desc'
}

export interface TableDataSourceMapping {
  type: 'table'
  columnConfig: { column: string; label: string; sortable?: boolean; format?: string }[]
}

export type DataSourceMapping = ChartDataSourceMapping | KpiDataSourceMapping | TableDataSourceMapping

// Links a widget to a live SQL query for on-demand refresh
export interface WidgetDataSource {
  connectionId: number
  sql: string
  mapping: DataSourceMapping
  lastRefreshedAt?: string
}

// Discriminated union — enables type narrowing in templates
export type WidgetConfig =
  | { type: 'kpi'; config: KpiWidgetConfig }
  | { type: 'chart'; config: ChartWidgetConfig }
  | { type: 'table'; config: TableWidgetConfig }
  | { type: 'text'; config: TextWidgetConfig }
  | { type: 'filter'; config: FilterWidgetConfig }

// A single widget placed in the grid
export interface DashboardWidget {
  id: string
  title?: string
  description?: string
  position: GridPosition
  widget: WidgetConfig
  dataSource?: WidgetDataSource
  sources?: string[]  // Which data context sources this widget uses
}

// A full dashboard with its widget collection
export interface Dashboard {
  id: number
  title: string
  description?: string
  widgets: DashboardWidget[]
  data_context?: Record<string, any> | null  // Dashboard-level semantic layer
  createdAt?: string
  updatedAt?: string
  // Schedule fields
  schedule_type?: 'preset' | 'cron' | null
  schedule_value?: string | null
  cron_expression?: string | null
  schedule_active?: boolean
  next_run_at?: string | null
  last_run_at?: string | null
}

// Run history for a scheduled dashboard refresh
export interface DashboardRefreshRun {
  id: string
  dashboard_id: number
  status: 'running' | 'completed' | 'failed'
  started_at: string
  completed_at?: string | null
  duration_ms?: number | null
  widgets_total?: number | null
  widgets_succeeded?: number | null
  widgets_failed?: number | null
  error?: string | null
  widget_errors?: Record<string, string> | null
}

// Lightweight representation for the dashboard card list view
export interface DashboardListItem {
  id: number
  title: string
  description?: string
  createdAt?: string
  widgetCount: number
  widgetTypes: WidgetType[]
  widgets: { type: WidgetType; position: GridPosition; chartType?: ChartType }[]
}

// Default grid sizes per widget type
export const WIDGET_DEFAULTS: Record<WidgetType, GridPosition> = {
  kpi:    { x: 0, y: 0, w: 3,  h: 2, minW: 2, minH: 2 },
  chart:  { x: 0, y: 0, w: 6,  h: 5, minW: 3, minH: 3 },
  table:  { x: 0, y: 0, w: 12, h: 5, minW: 4, minH: 3 },
  text:   { x: 0, y: 0, w: 4,  h: 3, minW: 2, minH: 2 },
  filter: { x: 0, y: 0, w: 12, h: 2, minW: 4, minH: 2 },
}

// Derive a DashboardListItem from a full Dashboard
export function toDashboardListItem(dashboard: Dashboard): DashboardListItem {
  const types = [...new Set(dashboard.widgets.map(w => w.widget.type))]
  return {
    id: dashboard.id,
    title: dashboard.title,
    description: dashboard.description,
    createdAt: dashboard.createdAt,
    widgetCount: dashboard.widgets.length,
    widgetTypes: types,
    widgets: dashboard.widgets.map(w => ({
      type: w.widget.type,
      position: w.position,
      chartType: w.widget.type === 'chart' ? (w.widget.config as ChartWidgetConfig).type : undefined,
    })),
  }
}
