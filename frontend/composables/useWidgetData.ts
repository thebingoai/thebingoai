import { ref, computed, watch } from 'vue'
import type { Ref } from 'vue'
import type { DashboardWidget } from '~/types/dashboard'
import { useApi } from '~/composables/useApi'
import { useDashboardStore } from '~/stores/dashboard'
import { mergeRefreshedConfig } from '~/utils/widgetMerge'
import { trackAbort, releaseAbort, isAbortError } from '~/utils/inflight'

export function useWidgetData(
  widget: Ref<DashboardWidget>,
  autoRefresh = true,
  opts: { dashboardId?: number | null } = {},
) {
  const localLoading = ref(false)
  const localError = ref<string | null>(null)
  const store = useDashboardStore()
  let refreshSeq = 0

  // widget.value may be null at setup — BriefingWidgetEmbed passes ref(null)
  // and loads the widget async onMounted. Guard so the immediate watcher and
  // these computeds don't deref null and crash the briefing view.
  const hasDataSource = computed(() => !!widget.value?.dataSource)
  const lastRefreshedAt = computed(() => widget.value?.dataSource?.lastRefreshedAt ?? null)
  const servedFrom = computed(() => widget.value?.dataSource?.servedFrom ?? null)
  // Also true while a bulk dashboard refresh covering this widget is in flight.
  const loading = computed(() => localLoading.value || !!store.refreshingWidgets[widget.value?.id])
  // A bulk refresh failure lands in the store: the watcher below is disabled
  // while bulk loading is on, so refresh() (the only writer of localError)
  // never runs for it. Without this the widget silently keeps its old value.
  const error = computed(() =>
    localError.value ?? (store.widgetErrors?.[widget.value?.id] ?? null),
  )

  async function refresh() {
    const ds = widget.value?.dataSource
    if (!ds) return

    const seq = ++refreshSeq
    // Bump the store-level seq so an in-flight bulk refresh won't overwrite
    // this newer single-widget result.
    store.widgetSeq[widget.value.id] = (store.widgetSeq[widget.value.id] ?? 0) + 1
    localLoading.value = true
    localError.value = null
    if (store.widgetErrors) delete store.widgetErrors[widget.value.id]

    const ctrl = trackAbort()
    try {
      const api = useApi()
      // An embed (chat chart, briefing) renders a widget of a dashboard that is
      // NOT the one the dashboard store is on — outside /dashboard the store is
      // reset, so deriving the id from it sends `undefined` and the backend
      // loses the DataPlane / cache / serving-org path for that dashboard.
      const dashboardId = opts.dashboardId ?? store.currentDashboardId ?? undefined
      // The store's filters belong to store.currentDashboardId, so they are only
      // valid when that IS this widget's dashboard; otherwise send none rather
      // than another dashboard's WHERE clauses. Known gap: an embed then renders
      // unfiltered. Rendering the referenced dashboard's own saved filters would
      // mean fetching that dashboard here — its filter values live in its own
      // localStorage key and need its filter-widget config to resolve.
      const ownFilters = dashboardId === (store.currentDashboardId ?? undefined)
      const filters = ownFilters && store.activeFilters.length > 0 ? store.activeFilters : undefined
      const chartType = widget.value.widget?.config?.type
      const mapping = chartType
        ? { ...ds.mapping, chartType }
        : ds.mapping
      const response = await api.dashboards.refreshWidget({
        connection_id: ds.connectionId,
        sql: ds.sql,
        mapping: mapping as any,
        filters,
        dashboard_id: dashboardId,
        widget_id: widget.value.id,  // required for the result cache key (else backend no-ops the cache)
        widget_sources: widget.value.sources ?? undefined,
      }, ctrl.signal) as { config: Record<string, any>; refreshed_at: string; served_from?: 'data_plane' | 'cache' | 'source'; source_columns?: string[]; source_rows?: any[][] }

      if (seq !== refreshSeq) return
      Object.assign(widget.value.widget.config, mergeRefreshedConfig(widget.value, response.config))
      ds.lastRefreshedAt = response.refreshed_at
      ds.servedFrom = response.served_from
      // Cache raw columns/rows so the Edit Widget panel opens without re-running SQL.
      if (response.source_columns) {
        store.setWidgetSourceData(widget.value.id, response.source_columns, response.source_rows ?? [])
      }
    } catch (err: any) {
      if (seq !== refreshSeq || isAbortError(err)) return  // stale or navigated-away: silent
      localError.value = err?.data?.detail ?? err?.message ?? 'Refresh failed'
    } finally {
      releaseAbort(ctrl)
      if (seq === refreshSeq) localLoading.value = false
    }
  }

  // Refresh on mount and whenever active filters change (SQL-backed widgets).
  // immediate: true triggers the initial fetch so widgets always render filtered,
  // fresh data instead of the unfiltered snapshot baked into widget.config at
  // generation time. refreshSeq inside refresh() discards stale responses if
  // activeFilters changes before the in-flight request returns.
  // With the per-Org bulk_widget_loading flag on, the dashboard orchestrates
  // one bulk refresh instead (openDashboard + the page-level filter watcher),
  // so the per-widget watcher stays quiet.
  // autoRefresh=false (briefing embeds with a generation-time snapshot) skips
  // the watcher entirely — the snapshot already populated the config, so a live
  // re-query would be redundant and slow.
  if (autoRefresh) {
    watch(
      () => JSON.stringify(store.activeFilters),
      () => {
        if (hasDataSource.value && !store.bulkWidgetLoading) refresh()
      },
      { immediate: true },
    )
  }

  return { loading, error, lastRefreshedAt, servedFrom, hasDataSource, refresh }
}
