import { describe, it, expect, vi, beforeEach } from 'vitest'
import { reactive, ref } from 'vue'

// useWidgetData is called by BriefingWidgetEmbed with ref(null) before the
// widget loads async onMounted. These tests lock in null-safety so the
// briefing view doesn't crash (regression: null.dataSource at setup).

const mockRefreshWidget = vi.fn().mockResolvedValue({ config: {}, refreshed_at: 'now' })
vi.mock('~/composables/useApi', () => ({
  useApi: () => ({
    fetchWithRefresh: vi.fn(),
    dashboards: { refreshWidget: mockRefreshWidget },
  }),
}))
// Only widgetErrors is reactive: the composable exposes `error` as a computed
// over it, and a plain object would never re-evaluate. The rest stays plain on
// purpose — every composable built by an earlier test leaves its activeFilters
// watcher behind, and a reactive activeFilters would fire them all on the next
// assignment, each refreshing with the store's dashboard id and burying the
// call the "dashboard scoping" tests then read as the last one.
const store = {
  refreshingWidgets: {} as Record<string, boolean>,
  widgetSeq: {} as Record<string, number>,
  widgetErrors: reactive({} as Record<string, string>),
  activeFilters: [] as any[],
  bulkWidgetLoading: false,
  currentDashboardId: null as number | null,
  setWidgetSourceData: vi.fn(),
}
vi.mock('~/stores/dashboard', () => ({
  useDashboardStore: () => store,
}))
vi.mock('~/utils/widgetMerge', () => ({
  mergeRefreshedConfig: (a: any) => a,
}))

import { useWidgetData } from '~/composables/useWidgetData'

describe('useWidgetData null-safety', () => {
  it('does not throw when widget.value is null', () => {
    const widget = ref<any>(null)
    expect(() => useWidgetData(widget)).not.toThrow()
  })

  it('computeds return falsy/null for a null widget', () => {
    const widget = ref<any>(null)
    const { hasDataSource, lastRefreshedAt, servedFrom } = useWidgetData(widget)
    expect(hasDataSource.value).toBe(false)
    expect(lastRefreshedAt.value).toBeNull()
    expect(servedFrom.value).toBeNull()
  })

  it('refresh() is a no-op when widget has no dataSource', async () => {
    const widget = ref<any>(null)
    const { refresh } = useWidgetData(widget)
    await expect(refresh()).resolves.toBeUndefined()
  })

  it('reflects dataSource once the widget loads', () => {
    const widget = ref<any>(null)
    const { hasDataSource, servedFrom } = useWidgetData(widget)
    widget.value = { id: 'w1', dataSource: { servedFrom: 'data_plane' } }
    expect(hasDataSource.value).toBe(true)
    expect(servedFrom.value).toBe('data_plane')
  })

  it('auto-refreshes on the immediate watcher when the widget already has a dataSource', async () => {
    mockRefreshWidget.mockClear()
    const widget = ref<any>({ id: 'w1', dataSource: { connectionId: 1, sql: 'select 1', mapping: {} }, widget: { config: {} } })
    useWidgetData(widget) // autoRefresh defaults true
    await Promise.resolve()
    expect(mockRefreshWidget).toHaveBeenCalledTimes(1)
  })

  it('does NOT auto-refresh when autoRefresh is false (briefing snapshot path)', async () => {
    mockRefreshWidget.mockClear()
    const widget = ref<any>({ id: 'w1', dataSource: { connectionId: 1, sql: 'select 1', mapping: {} }, widget: { config: {} } })
    useWidgetData(widget, false)
    await Promise.resolve()
    expect(mockRefreshWidget).not.toHaveBeenCalled()
  })

  it('sends widget_id so the backend can build the result-cache key', async () => {
    // Without widget_id the backend cache key is (None, None) and caching no-ops.
    mockRefreshWidget.mockClear()
    const widget = ref<any>({ id: 'w1', dataSource: { connectionId: 1, sql: 'select 1', mapping: {} }, widget: { config: {} } })
    useWidgetData(widget)
    await Promise.resolve()
    expect(mockRefreshWidget).toHaveBeenCalledWith(
      expect.objectContaining({ widget_id: 'w1' }),
      expect.anything(),
    )
  })
})

describe('useWidgetData bulk error surfacing', () => {
  beforeEach(() => {
    for (const k of Object.keys(store.widgetErrors)) delete store.widgetErrors[k]
    mockRefreshWidget.mockClear()
  })

  it('surfaces a bulk refresh error recorded in the store', () => {
    // Under bulk loading the watcher never calls refresh(), so the composable's
    // own error ref stays null and the widget's banner never appears.
    const widget = ref<any>({ id: 'w1', dataSource: { connectionId: 1, sql: 'select 1', mapping: {} }, widget: { config: {} } })
    const { error } = useWidgetData(widget, false)
    expect(error.value).toBeNull()
    store.widgetErrors['w1'] = 'relation "orders" does not exist'
    expect(error.value).toBe('relation "orders" does not exist')
  })

  it('clears the stored error when a manual refresh succeeds', async () => {
    const widget = ref<any>({ id: 'w1', dataSource: { connectionId: 1, sql: 'select 1', mapping: {} }, widget: { config: {} } })
    const { error, refresh } = useWidgetData(widget, false)
    store.widgetErrors['w1'] = 'boom'
    await refresh()
    expect(store.widgetErrors['w1']).toBeUndefined()
    expect(error.value).toBeNull()
  })
})

// An embed (chat chart, briefing) renders a widget belonging to a dashboard the
// store is NOT on — on /chat the store is reset entirely. Deriving dashboard_id
// from the store sent `undefined` (losing the DataPlane/cache/serving path) or,
// worse, another dashboard's active filters.
describe('useWidgetData dashboard scoping', () => {
  const liveWidget = () => ref<any>({
    id: 'w1',
    dataSource: { connectionId: 1, sql: 'select 1', mapping: {} },
    widget: { config: {} },
  })

  const payload = () => mockRefreshWidget.mock.calls.at(-1)![0]

  beforeEach(() => {
    mockRefreshWidget.mockClear()
    store.activeFilters = []
    store.currentDashboardId = null
  })

  it('sends the embed dashboard id even when the store has none', async () => {
    const { refresh } = useWidgetData(liveWidget(), false, { dashboardId: 42 })
    await refresh()
    expect(payload().dashboard_id).toBe(42)
  })

  it('falls back to the store id on the dashboard page', async () => {
    store.currentDashboardId = 7
    const { refresh } = useWidgetData(liveWidget(), false)
    await refresh()
    expect(payload().dashboard_id).toBe(7)
  })

  it('never sends another dashboard\'s filters to an embed', async () => {
    store.currentDashboardId = 7
    store.activeFilters = [{ column: 'created_at', operator: 'gte', value: '2026-01-01' }]
    const { refresh } = useWidgetData(liveWidget(), false, { dashboardId: 42 })
    await refresh()
    expect(payload().dashboard_id).toBe(42)
    expect(payload().filters).toBeUndefined()
  })

  it('still sends filters when the embed IS the open dashboard', async () => {
    store.currentDashboardId = 42
    store.activeFilters = [{ column: 'created_at', operator: 'gte', value: '2026-01-01' }]
    const { refresh } = useWidgetData(liveWidget(), false, { dashboardId: 42 })
    await refresh()
    expect(payload().filters).toHaveLength(1)
  })
})
