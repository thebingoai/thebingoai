import { ref, computed, watch } from 'vue'
import type { Ref } from 'vue'
import type { DashboardWidget } from '~/types/dashboard'
import { useApi } from '~/composables/useApi'
import { useSqlite } from '~/composables/useSqlite'
import { useDashboardStore } from '~/stores/dashboard'
import { injectFiltersForSqlite } from '~/utils/filterInjection'
import { transformWidgetData } from '~/utils/widgetTransform'

export function useWidgetData(widget: Ref<DashboardWidget>) {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const store = useDashboardStore()

  const hasDataSource = computed(() => !!widget.value.dataSource)
  const lastRefreshedAt = computed(() => widget.value.dataSource?.lastRefreshedAt ?? null)

  async function refresh() {
    const ds = widget.value.dataSource
    if (!ds) return

    loading.value = true
    error.value = null

    try {
      // Check if this is a DATASET connection (sql.js path)
      if (store.connectionTypes[ds.connectionId] === 'dataset') {
        const sqlite = useSqlite()
        const activeFilters = store.activeFilters
        let sql = ds.sql
        let params: any[] | undefined

        if (activeFilters.length > 0) {
          const injected = injectFiltersForSqlite(sql, activeFilters)
          sql = injected.sql
          params = injected.params
        }

        const result = await sqlite.executeQuery(ds.connectionId, sql, params)
        const config = transformWidgetData(result, ds.mapping as any)

        Object.assign(widget.value.widget.config, config)
        ds.lastRefreshedAt = new Date().toISOString()
      } else {
        // Regular database connection — use backend API
        const api = useApi()
        const filters = store.activeFilters.length > 0 ? store.activeFilters : undefined
        const response = await api.dashboards.refreshWidget({
          connection_id: ds.connectionId,
          sql: ds.sql,
          mapping: ds.mapping as any,
          filters,
        }) as { config: Record<string, any>; refreshed_at: string }

        Object.assign(widget.value.widget.config, response.config)
        ds.lastRefreshedAt = response.refreshed_at
      }
    } catch (err: any) {
      error.value = err?.data?.detail ?? err?.message ?? 'Refresh failed'
    } finally {
      loading.value = false
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

  return { loading, error, lastRefreshedAt, hasDataSource, refresh }
}
