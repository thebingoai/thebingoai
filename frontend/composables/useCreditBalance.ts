/**
 * useCreditBalance — fetches and exposes the workspace credit balance.
 *
 * Refreshes automatically after each conversation turn via `refresh()`.
 * The chat layer should call `refresh()` after receiving the `done` SSE event.
 */

interface BalanceResponse {
  used_today: number
  remaining: number
  resets_at: string
  org_exhausted?: boolean
  balance_scope?: 'workspace' | 'unlimited'
}

export const useCreditBalance = () => {
  const { fetchWithRefresh } = useApi()

  // Shared state across all useCreditBalance() instances (Nuxt useState)
  const usedToday = useState<number>('credit:usedToday', () => 0)
  const remaining = useState<number>('credit:remaining', () => 180)
  const resetsAt = useState<string>('credit:resetsAt', () => '')
  const loading = useState<boolean>('credit:loading', () => false)
  const error = useState<string | null>('credit:error', () => null)
  // Workspace (org) credit pool drained — lets the banner show a
  // workspace-specific message instead of "resets at midnight".
  const orgExhausted = useState<boolean>('credit:orgExhausted', () => false)
  // "workspace" → `remaining` is the org pool total and gates spending.
  // "unlimited" → no org pool; nothing gates the user, so the number is not a
  // real cap and the chat UI hides it.
  const balanceScope = useState<'workspace' | 'unlimited'>('credit:scope', () => 'workspace')

  const isUnlimited = computed(() => balanceScope.value === 'unlimited')
  // Never "exhausted" when unlimited — there is no cap to hit.
  const isExhausted = computed(() => !isUnlimited.value && remaining.value <= 0)

  async function fetchBalance(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const data = await fetchWithRefresh<BalanceResponse>('/api/credits/balance', {
        method: 'GET',
      })
      usedToday.value = data.used_today
      remaining.value = data.remaining
      resetsAt.value = data.resets_at
      orgExhausted.value = data.org_exhausted ?? false
      balanceScope.value = data.balance_scope ?? 'workspace'
    } catch (err: any) {
      error.value = err?.message ?? 'Failed to fetch credit balance'
    } finally {
      loading.value = false
    }
  }

  // Fetch on mount — only when called from a component setup. Callers that grab
  // just `refresh` (useChatStreaming, useBriefing) run outside setup, where
  // onMounted has no instance to bind to and Vue warns.
  if (getCurrentInstance()) {
    onMounted(() => {
      fetchBalance()
    })
  }

  return {
    usedToday,
    remaining,
    resetsAt,
    isExhausted,
    orgExhausted,
    balanceScope,
    isUnlimited,
    loading,
    error,
    refresh: fetchBalance,
  }
}
