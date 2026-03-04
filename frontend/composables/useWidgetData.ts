import { ref, computed } from 'vue'
import type { Ref } from 'vue'
import type { DashboardWidget } from '~/types/dashboard'
import { useApi } from '~/composables/useApi'

export function useWidgetData(widget: Ref<DashboardWidget>) {
  const loading = ref(false)
  const error = ref<string | null>(null)

  const hasDataSource = computed(() => !!widget.value.dataSource)

  const lastRefreshedAt = computed(() => widget.value.dataSource?.lastRefreshedAt ?? null)

  async function refresh() {
    const ds = widget.value.dataSource
    if (!ds) return

    const api = useApi()
    loading.value = true
    error.value = null

    try {
      const response = await api.dashboards.refreshWidget({
        connection_id: ds.connectionId,
        sql: ds.sql,
        mapping: ds.mapping as any,
      }) as { config: Record<string, any>; refreshed_at: string }

      // Merge new config into widget (config doubles as cache)
      Object.assign(widget.value.widget.config, response.config)
      ds.lastRefreshedAt = response.refreshed_at
    } catch (err: any) {
      error.value = err?.data?.detail ?? err?.message ?? 'Refresh failed'
    } finally {
      loading.value = false
    }
  }

  return { loading, error, lastRefreshedAt, hasDataSource, refresh }
}
