/**
 * useCreditBalance — fetches and exposes the user's daily credit balance.
 *
 * Refreshes automatically after each conversation turn via `refresh()`.
 * The chat layer should call `refresh()` after receiving the `done` SSE event.
 */

interface BalanceResponse {
  daily_limit: number
  used_today: number
  remaining: number
  resets_at: string
}

export const useCreditBalance = () => {
  const { fetchWithRefresh } = useApi()

  // Shared state across all useCreditBalance() instances (Nuxt useState)
  const dailyLimit = useState<number>('credit:dailyLimit', () => 180)
  const usedToday = useState<number>('credit:usedToday', () => 0)
  const remaining = useState<number>('credit:remaining', () => 180)
  const resetsAt = useState<string>('credit:resetsAt', () => '')
  const loading = useState<boolean>('credit:loading', () => false)
  const error = useState<string | null>('credit:error', () => null)

  const isExhausted = computed(() => remaining.value <= 0)

  async function fetchBalance(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const data = await fetchWithRefresh<BalanceResponse>('/api/credits/balance', {
        method: 'GET',
      })
      dailyLimit.value = data.daily_limit
      usedToday.value = data.used_today
      remaining.value = data.remaining
      resetsAt.value = data.resets_at
    } catch (err: any) {
      error.value = err?.message ?? 'Failed to fetch credit balance'
    } finally {
      loading.value = false
    }
  }

  // Fetch on mount
  onMounted(() => {
    fetchBalance()
  })

  return {
    dailyLimit,
    usedToday,
    remaining,
    resetsAt,
    isExhausted,
    loading,
    error,
    refresh: fetchBalance,
  }
}
