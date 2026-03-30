import { defineStore } from 'pinia'
import type { Dashboard, DashboardWidget, FilterControl, GridPosition, WidgetDataSource, WidgetType } from '~/types/dashboard'
import { WIDGET_DEFAULTS } from '~/types/dashboard'
import { useApi } from '~/composables/useApi'

export interface ActiveFilter {
  column: string
  dimension?: string  // References data_context.dimensions key
  op: 'eq' | 'neq' | 'gt' | 'gte' | 'lt' | 'lte' | 'ilike' | 'in'
  value: any
}

interface DashboardState {
  dashboards: Dashboard[]
  currentDashboardId: number | null
  editMode: boolean
  loading: boolean
  saving: boolean
  refreshing: boolean
  dirty: boolean
  filterValues: Record<string, any>  // control key → value (string | {from, to} | null)
  connectionTypes: Record<number, string>  // connectionId → db_type
}

export const useDashboardStore = defineStore('dashboard', {
  state: (): DashboardState => ({
    dashboards: [],
    currentDashboardId: null,
    editMode: false,
    loading: false,
    saving: false,
    refreshing: false,
    dirty: false,
    filterValues: {},
    connectionTypes: {},
  }),

  getters: {
    currentDashboard(state): Dashboard | null {
      if (!state.currentDashboardId) return null
      return state.dashboards.find(d => d.id === state.currentDashboardId) ?? null
    },

    currentWidgets(): DashboardWidget[] {
      return this.currentDashboard?.widgets ?? []
    },

    /** Resolve filterValues → ActiveFilter[] by looking up control column mappings */
    activeFilters(state): ActiveFilter[] {
      const dashboard = state.currentDashboardId
        ? state.dashboards.find(d => d.id === state.currentDashboardId)
        : null
      if (!dashboard) return []

      // Collect all filter controls from filter widgets
      const controls: FilterControl[] = []
      for (const dw of dashboard.widgets) {
        if (dw.widget.type === 'filter') {
          controls.push(...(dw.widget.config as any).controls)
        }
      }

      const result: ActiveFilter[] = []
      for (const control of controls) {
        const value = state.filterValues[control.key]
        if (value === null || value === undefined || value === '') continue
        if (!control.column) continue

        const dim = control.dimension || undefined
        if (control.type === 'dropdown') {
          if (Array.isArray(value) && value.length > 0) {
            result.push({ column: control.column, dimension: dim, op: 'in', value })
          } else if (typeof value === 'string' && value) {
            result.push({ column: control.column, dimension: dim, op: 'eq', value })
          }
        } else if (control.type === 'search') {
          result.push({ column: control.column, dimension: dim, op: 'ilike', value: `%${value}%` })
        } else if (control.type === 'date_range') {
          const { from, to } = value as { from?: string; to?: string }
          if (from) result.push({ column: control.column, dimension: dim, op: 'gte', value: from })
          if (to) result.push({ column: control.column, dimension: dim, op: 'lte', value: to })
        }
      }
      return result
    },
  },

  actions: {
    async fetchDashboards() {
      const api = useApi()
      this.loading = true
      try {
        const [data, connections] = await Promise.all([
          api.dashboards.list() as Promise<Dashboard[]>,
          api.connections.list() as Promise<any[]>,
        ])
        this.connectionTypes = Object.fromEntries(connections.map((c: any) => [c.id, c.db_type]))
        this.dashboards = data.map(d => ({
          ...d,
          widgets: (d.widgets ?? []).map(normalizeWidget),
          createdAt: (d as any).created_at,
          updatedAt: (d as any).updated_at,
        }))
      } finally {
        this.loading = false
      }
    },

    async fetchDashboard(id: number) {
      const api = useApi()
      this.loading = true
      try {
        const [data, connections] = await Promise.all([
          api.dashboards.get(id) as Promise<any>,
          api.connections.list() as Promise<any[]>,
        ])
        this.connectionTypes = Object.fromEntries(connections.map((c: any) => [c.id, c.db_type]))
        const dashboard: Dashboard = {
          ...data,
          widgets: (data.widgets ?? []).map(normalizeWidget),
          data_context: data.data_context ?? null,
          createdAt: data.created_at,
          updatedAt: data.updated_at,
        }
        const idx = this.dashboards.findIndex(d => d.id === id)
        if (idx >= 0) {
          this.dashboards[idx] = dashboard
        } else {
          this.dashboards.push(dashboard)
        }
        this.dirty = false
      } finally {
        this.loading = false
      }
    },

    async createDashboard(title: string) {
      const api = useApi()
      const data = await api.dashboards.create({ title }) as any
      const dashboard: Dashboard = {
        ...data,
        createdAt: data.created_at,
        updatedAt: data.updated_at,
      }
      this.dashboards.push(dashboard)
      return dashboard
    },

    async saveDashboard() {
      const dashboard = this.currentDashboard
      if (!dashboard) return
      const api = useApi()
      this.saving = true
      try {
        await api.dashboards.update(dashboard.id, {
          title: dashboard.title,
          description: dashboard.description,
          widgets: dashboard.widgets,
        })
        this.dirty = false
      } finally {
        this.saving = false
      }
    },

    async duplicateDashboard(id: number) {
      const source = this.dashboards.find(d => d.id === id)
      if (!source) return
      const api = useApi()
      const data = await api.dashboards.create({
        title: `${source.title} (Copy)`,
        description: source.description,
        widgets: JSON.parse(JSON.stringify(source.widgets)),
      }) as any
      const dashboard: Dashboard = {
        ...data,
        widgets: (data.widgets ?? []).map(normalizeWidget),
        createdAt: data.created_at,
        updatedAt: data.updated_at,
      }
      this.dashboards.push(dashboard)
      return dashboard
    },

    async deleteDashboard(id: number) {
      const api = useApi()
      await api.dashboards.delete(id)
      this.dashboards = this.dashboards.filter(d => d.id !== id)
      if (this.currentDashboardId === id) {
        this.currentDashboardId = null
        this.editMode = false
        this.dirty = false
      }
    },

    async openDashboard(id: number) {
      this.currentDashboardId = id
      this.editMode = false
      this.dirty = false
      // Restore persisted filters from localStorage
      try {
        const saved = localStorage.getItem(`bingo:dashboard:${id}:filters`)
        this.filterValues = saved ? JSON.parse(saved) : {}
      } catch {
        this.filterValues = {}
      }
      // Ensure full dashboard data is loaded (saved config already has data)
      await this.fetchDashboard(id)
    },

    setFilterValue(key: string, value: any) {
      this.filterValues = { ...this.filterValues, [key]: value }
      if (this.currentDashboardId) {
        try {
          localStorage.setItem(
            `bingo:dashboard:${this.currentDashboardId}:filters`,
            JSON.stringify(this.filterValues),
          )
        } catch { /* quota exceeded — ignore */ }
      }
    },

    clearFilters() {
      this.filterValues = {}
      if (this.currentDashboardId) {
        localStorage.removeItem(`bingo:dashboard:${this.currentDashboardId}:filters`)
      }
    },

    closeDashboard() {
      this.currentDashboardId = null
      this.editMode = false
      this.dirty = false
    },

    toggleEditMode() {
      this.editMode = !this.editMode
    },

    setEditMode(value: boolean) {
      this.editMode = value
    },

    addWidget(type: WidgetType) {
      const dashboard = this.currentDashboard
      if (!dashboard) return

      const id = `widget-${Date.now()}`
      const position = { ...WIDGET_DEFAULTS[type] }

      const maxY = dashboard.widgets.reduce((max, w) => {
        return Math.max(max, w.position.y + w.position.h)
      }, 0)
      position.y = maxY

      const newWidget: DashboardWidget = {
        id,
        position,
        widget: getDefaultWidgetConfig(type),
      }

      dashboard.widgets.push(newWidget)
      this.dirty = true
    },

    removeWidget(widgetId: string) {
      const dashboard = this.currentDashboard
      if (!dashboard) return
      dashboard.widgets = dashboard.widgets.filter(w => w.id !== widgetId)
      this.dirty = true
    },

    duplicateWidget(widgetId: string) {
      const dashboard = this.currentDashboard
      if (!dashboard) return
      const source = dashboard.widgets.find(w => w.id === widgetId)
      if (!source) return
      const clone: DashboardWidget = JSON.parse(JSON.stringify(source))
      clone.id = `widget-${Date.now()}`
      clone.position = { ...clone.position, y: clone.position.y + clone.position.h }
      dashboard.widgets.push(clone)
      this.dirty = true
    },

    updateWidgetPosition(widgetId: string, position: Partial<GridPosition>) {
      const dashboard = this.currentDashboard
      if (!dashboard) return
      const widget = dashboard.widgets.find(w => w.id === widgetId)
      if (!widget) return
      Object.assign(widget.position, position)
      this.dirty = true
    },

    updateWidgetConfig(widgetId: string, widget: DashboardWidget['widget']) {
      const dashboard = this.currentDashboard
      if (!dashboard) return
      const w = dashboard.widgets.find(w => w.id === widgetId)
      if (!w) return
      w.widget = widget
      this.dirty = true
    },

    updateWidgetMeta(widgetId: string, meta: { title?: string; description?: string }) {
      const dashboard = this.currentDashboard
      if (!dashboard) return
      const w = dashboard.widgets.find(w => w.id === widgetId)
      if (!w) return
      if (meta.title !== undefined) w.title = meta.title
      if (meta.description !== undefined) w.description = meta.description
      this.dirty = true
    },

    setWidgetDataSource(widgetId: string, dataSource: WidgetDataSource) {
      const dashboard = this.currentDashboard
      if (!dashboard) return
      const w = dashboard.widgets.find(w => w.id === widgetId)
      if (!w) return
      w.dataSource = dataSource
      this.dirty = true
    },

    updateWidgetSql(widgetId: string, sql: string) {
      const dashboard = this.currentDashboard
      if (!dashboard) return
      const w = dashboard.widgets.find(w => w.id === widgetId)
      if (!w?.dataSource) return
      w.dataSource.sql = sql
      this.dirty = true
    },

    async refreshAllWidgets() {
      const dashboard = this.currentDashboard
      if (!dashboard) return
      const api = useApi()
      this.refreshing = true

      try {
        const filters = this.activeFilters.length > 0 ? this.activeFilters : undefined
        const sqlWidgets = dashboard.widgets.filter(w => w.dataSource)

        await Promise.all(sqlWidgets.map(async (widget) => {
          if (!widget.dataSource) return
          try {
            const response = await api.dashboards.refreshWidget({
              connection_id: widget.dataSource.connectionId,
              sql: widget.dataSource.sql,
              mapping: widget.dataSource.mapping as any,
              filters,
              dashboard_id: this.currentDashboardId ?? undefined,
              widget_sources: widget.sources ?? undefined,
            }) as { config: Record<string, any>; refreshed_at: string }
            Object.assign(widget.widget.config, response.config)
            widget.dataSource.lastRefreshedAt = response.refreshed_at
          } catch (e) {
            console.error(`Widget ${widget.id} refresh failed:`, e)
          }
        }))
      } finally {
        this.refreshing = false
      }
    },

    async setSchedule(dashboardId: number, scheduleType: string, scheduleValue: string) {
      const api = useApi()
      const data = await api.dashboards.setSchedule(dashboardId, { schedule_type: scheduleType, schedule_value: scheduleValue }) as any
      const dashboard = this.dashboards.find(d => d.id === dashboardId)
      if (dashboard) {
        dashboard.schedule_type = data.schedule_type
        dashboard.schedule_value = data.schedule_value
        dashboard.cron_expression = data.cron_expression
        dashboard.schedule_active = data.schedule_active
        dashboard.next_run_at = data.next_run_at
        dashboard.last_run_at = data.last_run_at
      }
    },

    async toggleSchedule(dashboardId: number, active: boolean) {
      const api = useApi()
      const data = await api.dashboards.toggleSchedule(dashboardId, active) as any
      const dashboard = this.dashboards.find(d => d.id === dashboardId)
      if (dashboard) {
        dashboard.schedule_active = data.schedule_active
        dashboard.next_run_at = data.next_run_at
      }
    },

    $resetAll() {
      this.dashboards = []
      this.currentDashboardId = null
      this.editMode = false
      this.dirty = false
      this.filterValues = {}
      this.connectionTypes = {}
    },

    async removeSchedule(dashboardId: number) {
      const api = useApi()
      await api.dashboards.removeSchedule(dashboardId)
      const dashboard = this.dashboards.find(d => d.id === dashboardId)
      if (dashboard) {
        dashboard.schedule_type = null
        dashboard.schedule_value = null
        dashboard.cron_expression = null
        dashboard.schedule_active = false
        dashboard.next_run_at = null
      }
    },
  },
})

/** Migrate old flat widget format (no config wrapper) to current schema. */
function normalizeWidget(raw: any): DashboardWidget {
  const w = raw?.widget
  if (!w?.type) return raw as DashboardWidget

  // Step 1: ensure config sub-object exists
  let config = w.config
  if (!config) {
    const { type: _type, ...rest } = w
    config = rest
  }

  // Step 2: normalize old chart format
  // Old: { chartType, title, labels, datasets }
  // New: { type, title, data: { labels, datasets } }
  if (w.type === 'chart') {
    const { chartType, labels, datasets, type: cfgType, data, ...rest } = config
    const resolvedType = cfgType ?? chartType
    const resolvedData = data ?? (labels != null ? { labels, datasets: datasets ?? [] } : { labels: [], datasets: [] })
    config = { ...rest, ...(resolvedType ? { type: resolvedType } : {}), ...(resolvedData ? { data: resolvedData } : {}) }
  }

  return { ...raw, widget: { type: w.type, config }, dataSource: raw.dataSource } as DashboardWidget
}

function getDefaultWidgetConfig(type: WidgetType): DashboardWidget['widget'] {
  switch (type) {
    case 'kpi':
      return {
        type: 'kpi',
        config: { value: 0, label: 'New Score Chart' },
      }
    case 'chart':
      return {
        type: 'chart',
        config: {
          type: 'bar',
          title: 'New Chart',
          data: { labels: ['A', 'B', 'C'], datasets: [{ label: 'Series 1', data: [10, 20, 30] }] },
        },
      }
    case 'table':
      return {
        type: 'table',
        config: {
          columns: [{ key: 'name', label: 'Name' }, { key: 'value', label: 'Value' }],
          rows: [],
        },
      }
    case 'text':
      return {
        type: 'text',
        config: { content: 'Enter your text here...' },
      }
    case 'filter':
      return {
        type: 'filter',
        config: { controls: [] },
      }
  }
}
