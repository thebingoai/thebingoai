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
// reactive() because the composable exposes `error` as a computed: a plain
// object wouldn't re-evaluate it, and the real store is a reactive Pinia state.
const storeMock = reactive({
  refreshingWidgets: {} as Record<string, boolean>,
  widgetSeq: {} as Record<string, number>,
  widgetErrors: {} as Record<string, string>,
  activeFilters: [] as any[],
  bulkWidgetLoading: false,
  currentDashboardId: null as number | null,
})
vi.mock('~/stores/dashboard', () => ({
  useDashboardStore: () => storeMock,
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
    storeMock.widgetErrors = {}
    mockRefreshWidget.mockClear()
  })

  it('surfaces a bulk refresh error recorded in the store', () => {
    // Under bulk loading the watcher never calls refresh(), so the composable's
    // own error ref stays null and the widget's banner never appears.
    const widget = ref<any>({ id: 'w1', dataSource: { connectionId: 1, sql: 'select 1', mapping: {} }, widget: { config: {} } })
    const { error } = useWidgetData(widget, false)
    expect(error.value).toBeNull()
    storeMock.widgetErrors['w1'] = 'relation "orders" does not exist'
    expect(error.value).toBe('relation "orders" does not exist')
  })

  it('clears the stored error when a manual refresh succeeds', async () => {
    const widget = ref<any>({ id: 'w1', dataSource: { connectionId: 1, sql: 'select 1', mapping: {} }, widget: { config: {} } })
    const { error, refresh } = useWidgetData(widget, false)
    storeMock.widgetErrors['w1'] = 'boom'
    await refresh()
    expect(storeMock.widgetErrors['w1']).toBeUndefined()
    expect(error.value).toBeNull()
  })
})
