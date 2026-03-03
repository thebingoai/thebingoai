import { defineStore } from 'pinia'
import type { Dashboard, DashboardWidget, GridPosition, WidgetType } from '~/types/dashboard'
import { WIDGET_DEFAULTS } from '~/types/dashboard'
import { useApi } from '~/composables/useApi'

interface DashboardState {
  dashboards: Dashboard[]
  currentDashboardId: number | null
  editMode: boolean
  loading: boolean
  saving: boolean
  dirty: boolean
}

export const useDashboardStore = defineStore('dashboard', {
  state: (): DashboardState => ({
    dashboards: [],
    currentDashboardId: null,
    editMode: false,
    loading: false,
    saving: false,
    dirty: false,
  }),

  getters: {
    currentDashboard(state): Dashboard | null {
      if (!state.currentDashboardId) return null
      return state.dashboards.find(d => d.id === state.currentDashboardId) ?? null
    },

    currentWidgets(): DashboardWidget[] {
      return this.currentDashboard?.widgets ?? []
    },
  },

  actions: {
    async fetchDashboards() {
      const api = useApi()
      this.loading = true
      try {
        const data = await api.dashboards.list() as Dashboard[]
        this.dashboards = data.map(d => ({
          ...d,
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
        const data = await api.dashboards.get(id) as any
        const dashboard: Dashboard = {
          ...data,
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

    openDashboard(id: number) {
      this.currentDashboardId = id
      this.editMode = false
      this.dirty = false
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

    updateWidgetPosition(widgetId: string, position: Partial<GridPosition>) {
      const dashboard = this.currentDashboard
      if (!dashboard) return
      const widget = dashboard.widgets.find(w => w.id === widgetId)
      if (!widget) return
      Object.assign(widget.position, position)
      this.dirty = true
    },
  },
})

function getDefaultWidgetConfig(type: WidgetType): DashboardWidget['widget'] {
  switch (type) {
    case 'kpi':
      return {
        type: 'kpi',
        config: { value: 0, label: 'New KPI' },
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
