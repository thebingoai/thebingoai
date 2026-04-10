/**
 * useCreditSettings — API calls for the credits settings page.
 * Handles credit balance, usage history, and API key management.
 */

interface UsageItem {
  id: number
  title: string
  credits_used: number
  date: string
  created_at: string
}

interface HistoryResponse {
  items: UsageItem[]
  total: number
  page: number
  per_page: number
}

interface ApiKeyItem {
  provider: string
  masked_key: string
  api_base_url: string | null
  is_active: boolean
}

export const useCreditSettings = () => {
  const { fetchWithRefresh } = useApi()

  // ----- Balance -----
  const dailyLimit = ref<number>(180)
  const usedToday = ref<number>(0)
  const remaining = ref<number>(180)
  const balanceLoading = ref(false)

  const usedPercent = computed(() =>
    dailyLimit.value > 0 ? Math.min(100, (usedToday.value / dailyLimit.value) * 100) : 0
  )

  async function fetchBalance() {
    balanceLoading.value = true
    try {
      const data = await fetchWithRefresh<any>('/api/credits/balance', { method: 'GET' })
      dailyLimit.value = data.daily_limit
      usedToday.value = data.used_today
      remaining.value = data.remaining
    } finally {
      balanceLoading.value = false
    }
  }

  // ----- Usage history -----
  const historyItems = ref<UsageItem[]>([])
  const historyTotal = ref(0)
  const historyPage = ref(1)
  const historyPerPage = ref(20)
  const historyLoading = ref(false)

  async function fetchHistory(page = 1) {
    historyLoading.value = true
    try {
      const data = await fetchWithRefresh<HistoryResponse>(
        `/api/credits/history?page=${page}&per_page=${historyPerPage.value}`,
        { method: 'GET' }
      )
      historyItems.value = data.items
      historyTotal.value = data.total
      historyPage.value = data.page
    } finally {
      historyLoading.value = false
    }
  }

  const historyTotalPages = computed(() => Math.ceil(historyTotal.value / historyPerPage.value))

  async function nextPage() {
    if (historyPage.value < historyTotalPages.value) {
      await fetchHistory(historyPage.value + 1)
    }
  }

  async function prevPage() {
    if (historyPage.value > 1) {
      await fetchHistory(historyPage.value - 1)
    }
  }

  // ----- Daily totals (chart) -----
  const dailyTotals = ref<{ date: string; total: number }[]>([])
  const dailyTotalsLoading = ref(false)

  async function fetchDailyTotals(startDate?: string, endDate?: string) {
    dailyTotalsLoading.value = true
    try {
      const params = new URLSearchParams()
      if (startDate) params.set('start_date', startDate)
      if (endDate) params.set('end_date', endDate)
      const qs = params.toString() ? `?${params.toString()}` : ''
      dailyTotals.value = await fetchWithRefresh<{ date: string; total: number }[]>(
        `/api/credits/history/daily${qs}`,
        { method: 'GET' }
      )
    } finally {
      dailyTotalsLoading.value = false
    }
  }

  // ----- API keys -----
  const apiKeys = ref<ApiKeyItem[]>([])
  const keysLoading = ref(false)

  async function fetchApiKeys() {
    keysLoading.value = true
    try {
      apiKeys.value = await fetchWithRefresh<ApiKeyItem[]>('/api/credits/api-keys', { method: 'GET' })
    } finally {
      keysLoading.value = false
    }
  }

  async function saveApiKey(provider: string, apiKey: string, apiBaseUrl?: string) {
    await fetchWithRefresh('/api/credits/api-keys', {
      method: 'POST',
      body: { provider, api_key: apiKey, api_base_url: apiBaseUrl || null },
    })
    await fetchApiKeys()
  }

  async function deleteApiKey(provider: string) {
    await fetchWithRefresh(`/api/credits/api-keys/${provider}`, { method: 'DELETE' })
    await fetchApiKeys()
  }

  // ----- Init -----
  onMounted(async () => {
    await Promise.all([fetchBalance(), fetchHistory(), fetchDailyTotals(), fetchApiKeys()])
  })

  return {
    // Balance
    dailyLimit, usedToday, remaining, usedPercent, balanceLoading, fetchBalance,
    // History
    historyItems, historyTotal, historyPage, historyPerPage, historyTotalPages,
    historyLoading, fetchHistory, nextPage, prevPage,
    // Daily totals
    dailyTotals, dailyTotalsLoading, fetchDailyTotals,
    // API keys
    apiKeys, keysLoading, saveApiKey, deleteApiKey, fetchApiKeys,
  }
}
