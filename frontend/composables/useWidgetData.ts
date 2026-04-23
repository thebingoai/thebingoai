import { ref, computed, watch, onMounted } from 'vue'
import type { Ref } from 'vue'
import type { DashboardWidget } from '~/types/dashboard'
import { useApi } from '~/composables/useApi'
import { useDashboardStore } from '~/stores/dashboard'

export function useWidgetData(widget: Ref<DashboardWidget>) {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const store = useDashboardStore()
  let refreshSeq = 0

  const hasDataSource = computed(() => !!widget.value.dataSource)
  const lastRefreshedAt = computed(() => widget.value.dataSource?.lastRefreshedAt ?? null)

  async function refresh() {
    const ds = widget.value.dataSource
    if (!ds) return

    const seq = ++refreshSeq
    loading.value = true
    error.value = null

    try {
      const api = useApi()
      const filters = store.activeFilters.length > 0 ? store.activeFilters : undefined
      const chartType = widget.value.widget?.config?.type
      const mapping = chartType
        ? { ...ds.mapping, chartType }
        : ds.mapping
      const response = await api.dashboards.refreshWidget({
        connection_id: ds.connectionId,
        sql: ds.sql,
        mapping: mapping as any,
        filters,
        dashboard_id: store.currentDashboardId ?? undefined,
        widget_sources: widget.value.sources ?? undefined,
      }) as { config: Record<string, any>; refreshed_at: string }

      if (seq !== refreshSeq) return
      Object.assign(widget.value.widget.config, response.config)
      ds.lastRefreshedAt = response.refreshed_at
    } catch (err: any) {
      if (seq !== refreshSeq) return
      error.value = err?.data?.detail ?? err?.message ?? 'Refresh failed'
    } finally {
      if (seq === refreshSeq) loading.value = false
    }
  }

  // Re-run refresh when active filters change (only for SQL-backed widgets).
  // Serialize to string so the watcher only fires when values actually change,
  // not when the getter recomputes due to unrelated widget array mutations.
  watch(() => JSON.stringify(store.activeFilters), (newVal, oldVal) => {
    if (hasDataSource.value && newVal !== oldVal) {
      refresh()
    }
  })

  // If filters were restored from localStorage before this widget mounted,
  // the watch above won't fire (no change detected). Apply them immediately.
  onMounted(() => {
    if (hasDataSource.value && store.activeFilters.length > 0) {
      refresh()
    }
  })

  return { loading, error, lastRefreshedAt, hasDataSource, refresh }
}
