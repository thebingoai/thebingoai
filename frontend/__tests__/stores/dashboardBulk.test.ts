import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// ── Global mocks ────────────────────────────────────────────────────
vi.stubGlobal('localStorage', {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
})

const refreshAllMock = vi.fn()
const getDashboardMock = vi.fn()
const listConnectionsMock = vi.fn(async () => [])

vi.mock('~/composables/useApi', () => ({
  useApi: () => ({
    dashboards: { refreshAll: refreshAllMock, get: getDashboardMock },
    connections: { list: listConnectionsMock },
  }),
}))

import { useDashboardStore } from '~/stores/dashboard'
import type { Dashboard, DashboardWidget } from '~/types/dashboard'

function makeSqlWidget(id: string, overrides: Partial<DashboardWidget> = {}): DashboardWidget {
  return {
    id,
    position: { x: 0, y: 0, w: 3, h: 2 },
    widget: { type: 'kpi', config: { value: 1, label: 'Old' } },
    dataSource: { connectionId: 7, sql: 'SELECT 1', mapping: {} },
    ...overrides,
  } as DashboardWidget
}

function makeDashboard(widgets: DashboardWidget[], overrides: Partial<Dashboard> = {}): Dashboard {
  return { id: 1, title: 'D', widgets, ...overrides }
}

function setup(widgets: DashboardWidget[], overrides: Partial<Dashboard> = {}) {
  const store = useDashboardStore()
  store.dashboards = [makeDashboard(widgets, overrides)]
  store.currentDashboardId = 1
  return store
}

describe('refreshAllWidgets (bulk loading)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    refreshAllMock.mockReset()
    getDashboardMock.mockReset()
  })

  it('applies config, refreshed_at and served_from per widget', async () => {
    const store = setup([makeSqlWidget('w-1')])
    refreshAllMock.mockResolvedValueOnce({
      widgets: { 'w-1': { config: { value: 99 }, refreshed_at: '2026-06-11T00:00:00Z', served_from: 'data_plane' } },
    })

    await store.refreshAllWidgets()

    const w = store.currentWidgets[0]
    expect((w.widget.config as any).value).toBe(99)
    expect(w.dataSource!.lastRefreshedAt).toBe('2026-06-11T00:00:00Z')
    expect(w.dataSource!.servedFrom).toBe('data_plane')
  })

  it('preserves editor-only table column fields on bulk apply', async () => {
    const table = makeSqlWidget('w-t', {
      widget: {
        type: 'table',
        config: {
          columns: [{ key: 'amt', label: 'Amount', aggregation: 'sum', align: 'right' }],
          rows: [],
        },
      },
    } as any)
    const store = setup([table])
    refreshAllMock.mockResolvedValueOnce({
      widgets: {
        'w-t': {
          config: { columns: [{ key: 'amt', label: 'amt' }], rows: [{ amt: 5 }] },
          refreshed_at: 'x',
          served_from: 'source',
        },
      },
    })

    await store.refreshAllWidgets()

    const cols = (store.currentWidgets[0].widget.config as any).columns
    expect(cols[0].aggregation).toBe('sum')
    expect(cols[0].align).toBe('right')
    expect(cols[0].label).toBe('Amount') // data-only merge: saved label/edit wins, backend supplies data only
    expect((store.currentWidgets[0].widget.config as any).rows).toEqual([{ amt: 5 }])
  })

  it('skips widgets whose single-widget seq advanced mid-bulk', async () => {
    const store = setup([makeSqlWidget('w-1')])
    let resolveBulk!: (v: any) => void
    refreshAllMock.mockReturnValueOnce(new Promise(r => { resolveBulk = r }))

    const bulk = store.refreshAllWidgets()
    // A newer per-widget refresh lands while the bulk is in flight.
    store.widgetSeq['w-1'] = (store.widgetSeq['w-1'] ?? 0) + 1
    resolveBulk({ widgets: { 'w-1': { config: { value: 99 }, refreshed_at: 'x', served_from: 'cache' } } })
    await bulk

    expect((store.currentWidgets[0].widget.config as any).value).toBe(1) // untouched
  })

  it('newer bulk supersedes an older in-flight bulk', async () => {
    const store = setup([makeSqlWidget('w-1'), makeFilter()])
    let resolveOld!: (v: any) => void
    refreshAllMock
      .mockReturnValueOnce(new Promise(r => { resolveOld = r }))
      .mockResolvedValueOnce({ widgets: { 'w-1': { config: { value: 2 }, refreshed_at: 'b', served_from: 'cache' } } })

    const oldBulk = store.refreshAllWidgets()          // filters: none
    store.filterValues = { region: 'APAC' }            // changes activeFilters → different request key
    const newBulk = store.refreshAllWidgets()
    await newBulk
    resolveOld({ widgets: { 'w-1': { config: { value: 1_000 }, refreshed_at: 'a', served_from: 'cache' } } })
    await oldBulk

    expect((store.currentWidgets[0].widget.config as any).value).toBe(2) // newer bulk wins
    expect(store.refreshing).toBe(false)
    expect(store.refreshingWidgets).toEqual({})
  })

  it('dedups concurrent identical bulk requests', async () => {
    const store = setup([makeSqlWidget('w-1')])
    let resolveBulk!: (v: any) => void
    refreshAllMock.mockReturnValueOnce(new Promise(r => { resolveBulk = r }))

    const first = store.refreshAllWidgets()
    const second = store.refreshAllWidgets() // same dashboard + same filters → deduped
    resolveBulk({ widgets: {} })
    await Promise.all([first, second])

    expect(refreshAllMock).toHaveBeenCalledTimes(1)
  })

  it('marks widgets as refreshing while the bulk is in flight', async () => {
    const store = setup([makeSqlWidget('w-1')])
    let resolveBulk!: (v: any) => void
    refreshAllMock.mockReturnValueOnce(new Promise(r => { resolveBulk = r }))

    const bulk = store.refreshAllWidgets()
    expect(store.refreshingWidgets['w-1']).toBe(true)
    expect(store.refreshing).toBe(true)
    resolveBulk({ widgets: {} })
    await bulk
    expect(store.refreshingWidgets['w-1']).toBeUndefined()
    expect(store.refreshing).toBe(false)
  })

  function makeFilter(): DashboardWidget {
    return {
      id: 'w-filter',
      position: { x: 0, y: 0, w: 12, h: 2 },
      widget: { type: 'filter', config: { controls: [{ key: 'region', type: 'dropdown', column: 'region' }] } },
    } as DashboardWidget
  }
})

describe('openDashboard bulk gating', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    refreshAllMock.mockReset()
    getDashboardMock.mockReset()
  })

  it('triggers one bulk refresh when bulk_widget_loading is on', async () => {
    const store = useDashboardStore()
    getDashboardMock.mockResolvedValueOnce({
      id: 1, title: 'D', widgets: [], bulk_widget_loading: true,
      created_at: 'c', updated_at: 'u',
    })
    refreshAllMock.mockResolvedValueOnce({ widgets: {} })

    await store.openDashboard(1)
    await vi.waitFor(() => expect(refreshAllMock).toHaveBeenCalledTimes(1))
  })

  it('does not bulk refresh when the flag is off (legacy per-widget path)', async () => {
    const store = useDashboardStore()
    getDashboardMock.mockResolvedValueOnce({
      id: 1, title: 'D', widgets: [], created_at: 'c', updated_at: 'u',
    })

    await store.openDashboard(1)

    expect(refreshAllMock).not.toHaveBeenCalled()
  })
})

describe('refreshAllWidgets (per-widget failures)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    refreshAllMock.mockReset()
    getDashboardMock.mockReset()
  })

  it('records a per-widget error instead of only logging it', async () => {
    // The bulk endpoint reports failures per widget. The per-widget watcher is
    // off while bulk loading is on, so a console.error was the only trace: the
    // widget kept painting its previous value under its previous timestamp.
    const store = setup([makeSqlWidget('w-1')])
    refreshAllMock.mockResolvedValueOnce({
      widgets: { 'w-1': { error: 'relation "orders" does not exist' } },
    })

    await store.refreshAllWidgets()

    expect(store.widgetErrors['w-1']).toBe('relation "orders" does not exist')
    expect((store.currentWidgets[0].widget.config as any).value).toBe(1) // untouched
    expect(store.currentWidgets[0].dataSource!.lastRefreshedAt).toBeUndefined()
  })

  it('clears a recorded error once the widget refreshes successfully', async () => {
    const store = setup([makeSqlWidget('w-1')])
    store.widgetErrors['w-1'] = 'boom'
    refreshAllMock.mockResolvedValueOnce({
      widgets: { 'w-1': { config: { value: 42 }, refreshed_at: 'now', served_from: 'source' } },
    })

    await store.refreshAllWidgets()

    expect(store.widgetErrors['w-1']).toBeUndefined()
    expect((store.currentWidgets[0].widget.config as any).value).toBe(42)
  })

  it('marks every widget when the whole bulk request fails', async () => {
    // A per-widget error had a banner; a failed request had only a console
    // line, so every widget kept its old value and its old timestamp with
    // nothing on screen to say the refresh never happened.
    const store = setup([makeSqlWidget('w-1'), makeSqlWidget('w-2')])
    refreshAllMock.mockRejectedValueOnce({ data: { detail: 'connection refused' } })

    await store.refreshAllWidgets()

    expect(store.widgetErrors['w-1']).toBe('connection refused')
    expect(store.widgetErrors['w-2']).toBe('connection refused')
    expect((store.currentWidgets[0].widget.config as any).value).toBe(1)
    expect(store.refreshingWidgets['w-1']).toBeUndefined()
    expect(store.refreshing).toBe(false)
  })

  it('says nothing when the bulk request was aborted', async () => {
    // Navigation and $resetAll abort in flight requests; that is not a failure
    // the user should see a banner for.
    const store = setup([makeSqlWidget('w-1')])
    const abort = new Error('aborted')
    abort.name = 'AbortError'
    refreshAllMock.mockRejectedValueOnce(abort)

    await store.refreshAllWidgets()

    expect(store.widgetErrors['w-1']).toBeUndefined()
    expect(store.refreshing).toBe(false)
  })
})
