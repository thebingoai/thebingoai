import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// ── Global mocks ────────────────────────────────────────────────────
vi.stubGlobal('localStorage', {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
})

vi.mock('~/composables/useApi', () => ({
  useApi: () => ({ dashboards: {}, connections: {} }),
}))

import { useDashboardStore } from '~/stores/dashboard'
import type { Dashboard, DashboardWidget } from '~/types/dashboard'

// ── Helpers ─────────────────────────────────────────────────────────
function makeDashboard(overrides: Partial<Dashboard> = {}): Dashboard {
  return {
    id: 1,
    title: 'Test Dashboard',
    widgets: [],
    ...overrides,
  }
}

function makeFilterWidget(controls: any[]): DashboardWidget {
  return {
    id: 'w-filter',
    position: { x: 0, y: 0, w: 12, h: 2 },
    widget: { type: 'filter', config: { controls } },
  }
}

describe('dashboard store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // ── Initial state ──────────────────────────────────────────────────
  it('has correct initial state', () => {
    const store = useDashboardStore()
    expect(store.dashboards).toEqual([])
    expect(store.currentDashboardId).toBeNull()
    expect(store.editMode).toBe(false)
    expect(store.loading).toBe(false)
    expect(store.saving).toBe(false)
    expect(store.dirty).toBe(false)
    expect(store.filterValues).toEqual({})
    expect(store.connectionTypes).toEqual({})
  })

  // ── currentDashboard ──────────────────────────────────────────────
  it('currentDashboard returns null when no id set', () => {
    const store = useDashboardStore()
    store.dashboards = [makeDashboard()]
    expect(store.currentDashboard).toBeNull()
  })

  it('currentDashboard returns matching dashboard', () => {
    const store = useDashboardStore()
    const dashboard = makeDashboard({ id: 42, title: 'My Board' })
    store.dashboards = [dashboard]
    store.currentDashboardId = 42
    expect(store.currentDashboard).toEqual(dashboard)
  })

  it('currentDashboard returns null when id does not match', () => {
    const store = useDashboardStore()
    store.dashboards = [makeDashboard({ id: 1 })]
    store.currentDashboardId = 999
    expect(store.currentDashboard).toBeNull()
  })

  // ── currentWidgets ────────────────────────────────────────────────
  it('currentWidgets returns empty when no dashboard selected', () => {
    const store = useDashboardStore()
    expect(store.currentWidgets).toEqual([])
  })

  it('currentWidgets returns widgets of current dashboard', () => {
    const store = useDashboardStore()
    const widget: DashboardWidget = {
      id: 'w-1',
      position: { x: 0, y: 0, w: 3, h: 2 },
      widget: { type: 'kpi', config: { value: 42, label: 'Score' } },
    }
    store.dashboards = [makeDashboard({ id: 1, widgets: [widget] })]
    store.currentDashboardId = 1
    expect(store.currentWidgets).toHaveLength(1)
    expect(store.currentWidgets[0].id).toBe('w-1')
  })

  // ── activeFilters ─────────────────────────────────────────────────
  it('activeFilters returns empty when no dashboard selected', () => {
    const store = useDashboardStore()
    expect(store.activeFilters).toEqual([])
  })

  it('activeFilters resolves dropdown filter to eq', () => {
    const store = useDashboardStore()
    store.dashboards = [makeDashboard({
      id: 1,
      widgets: [makeFilterWidget([
        { key: 'region', type: 'dropdown', column: 'region' },
      ])],
    })]
    store.currentDashboardId = 1
    store.filterValues = { region: 'APAC' }
    expect(store.activeFilters).toEqual([
      { column: 'region', dimension: undefined, op: 'eq', value: 'APAC' },
    ])
  })

  it('activeFilters resolves dropdown array filter to in', () => {
    const store = useDashboardStore()
    store.dashboards = [makeDashboard({
      id: 1,
      widgets: [makeFilterWidget([
        { key: 'region', type: 'dropdown', column: 'region' },
      ])],
    })]
    store.currentDashboardId = 1
    store.filterValues = { region: ['APAC', 'EMEA'] }
    expect(store.activeFilters).toEqual([
      { column: 'region', dimension: undefined, op: 'in', value: ['APAC', 'EMEA'] },
    ])
  })

  it('activeFilters resolves search filter to ilike with % wrapping', () => {
    const store = useDashboardStore()
    store.dashboards = [makeDashboard({
      id: 1,
      widgets: [makeFilterWidget([
        { key: 'search', type: 'search', column: 'name' },
      ])],
    })]
    store.currentDashboardId = 1
    store.filterValues = { search: 'hello' }
    expect(store.activeFilters).toEqual([
      { column: 'name', dimension: undefined, op: 'ilike', value: '%hello%' },
    ])
  })

  it('activeFilters resolves date_range filter to gte/lte pair', () => {
    const store = useDashboardStore()
    store.dashboards = [makeDashboard({
      id: 1,
      widgets: [makeFilterWidget([
        { key: 'dates', type: 'date_range', column: 'order_date' },
      ])],
    })]
    store.currentDashboardId = 1
    store.filterValues = { dates: { from: '2024-01-01', to: '2024-12-31' } }
    expect(store.activeFilters).toEqual([
      { column: 'order_date', dimension: undefined, op: 'gte', value: '2024-01-01' },
      { column: 'order_date', dimension: undefined, op: 'lte', value: '2024-12-31' },
    ])
  })

  it('activeFilters skips controls with empty values', () => {
    const store = useDashboardStore()
    store.dashboards = [makeDashboard({
      id: 1,
      widgets: [makeFilterWidget([
        { key: 'region', type: 'dropdown', column: 'region' },
        { key: 'search', type: 'search', column: 'name' },
      ])],
    })]
    store.currentDashboardId = 1
    store.filterValues = { region: '', search: null }
    expect(store.activeFilters).toEqual([])
  })

  // ── addWidget ─────────────────────────────────────────────────────
  it('addWidget adds a widget and sets dirty', () => {
    const store = useDashboardStore()
    store.dashboards = [makeDashboard({ id: 1, widgets: [] })]
    store.currentDashboardId = 1
    expect(store.dirty).toBe(false)

    store.addWidget('kpi')

    expect(store.currentWidgets).toHaveLength(1)
    expect(store.currentWidgets[0].widget.type).toBe('kpi')
    expect(store.dirty).toBe(true)
  })

  // ── removeWidget ──────────────────────────────────────────────────
  it('removeWidget removes widget and sets dirty', () => {
    const store = useDashboardStore()
    const widget: DashboardWidget = {
      id: 'w-1',
      position: { x: 0, y: 0, w: 3, h: 2 },
      widget: { type: 'kpi', config: { value: 42, label: 'Score' } },
    }
    store.dashboards = [makeDashboard({ id: 1, widgets: [widget] })]
    store.currentDashboardId = 1

    store.removeWidget('w-1')

    expect(store.currentWidgets).toHaveLength(0)
    expect(store.dirty).toBe(true)
  })

  // ── $resetAll ─────────────────────────────────────────────────────
  it('$resetAll clears all state', () => {
    const store = useDashboardStore()
    store.dashboards = [makeDashboard()]
    store.currentDashboardId = 1
    store.editMode = true
    store.dirty = true
    store.filterValues = { region: 'APAC' }
    store.connectionTypes = { 1: 'postgres' }

    store.$resetAll()

    expect(store.dashboards).toEqual([])
    expect(store.currentDashboardId).toBeNull()
    expect(store.editMode).toBe(false)
    expect(store.dirty).toBe(false)
    expect(store.filterValues).toEqual({})
    expect(store.connectionTypes).toEqual({})
  })
})
