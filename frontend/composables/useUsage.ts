import type { UsageSummary, DailyUsage } from '~/types/usage'

export const useUsageNew = () => {
  const auth = useAuthNew()
  const summary = ref<UsageSummary | null>(null)
  const dailyUsage = ref<DailyUsage[]>([])
  const loading = ref(false)

  async function loadSummary(days: number = 30) {
    loading.value = true
    try {
      summary.value = await auth.apiRequest<UsageSummary>(`/api/usage/summary?days=${days}`)
    } finally {
      loading.value = false
    }
  }

  async function loadDailyUsage(days: number = 30) {
    loading.value = true
    try {
      const response = await auth.apiRequest<{ daily_usage: DailyUsage[] }>(`/api/usage/daily?days=${days}`)
      dailyUsage.value = response.daily_usage
    } finally {
      loading.value = false
    }
  }

  return {
    summary,
    dailyUsage,
    loading,
    loadSummary,
    loadDailyUsage
  }
}
