import type { ChartConfig } from './chart'

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
}

// Chart widget — alias for existing ChartConfig (zero migration cost)
export type ChartWidgetConfig = ChartConfig

// Table widget
export interface TableColumn {
  key: string
  label: string
  sortable?: boolean
  format?: 'number' | 'currency' | 'percent' | 'date' | 'text'
}

export interface TableWidgetConfig {
  columns: TableColumn[]
  rows: Record<string, any>[]
  pagination?: boolean
}

// Text/markdown widget
export interface TextWidgetConfig {
  content: string
  alignment?: 'left' | 'center' | 'right'
}

// Filter widget (placeholder for Phase 5)
export interface FilterControl {
  type: 'date_range' | 'dropdown' | 'search'
  label: string
  key: string
  options?: string[]
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
  trendValueColumn?: string
  sparklineColumn?: string
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
}

// A full dashboard with its widget collection
export interface Dashboard {
  id: number
  title: string
  description?: string
  widgets: DashboardWidget[]
  createdAt?: string
  updatedAt?: string
}

// Lightweight representation for the dashboard card list view
export interface DashboardListItem {
  id: number
  title: string
  description?: string
  widgetCount: number
  widgetTypes: WidgetType[]
}

// Default grid sizes per widget type
export const WIDGET_DEFAULTS: Record<WidgetType, GridPosition> = {
  kpi:    { x: 0, y: 0, w: 3,  h: 2, minW: 2, minH: 2 },
  chart:  { x: 0, y: 0, w: 6,  h: 4, minW: 3, minH: 3 },
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
    widgetCount: dashboard.widgets.length,
    widgetTypes: types,
  }
}
