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

/**
 * Initial value for every `credit:*` key, in one place so `clearCreditState`
 * cannot drift from the declarations below. Adding a key here is enough to have
 * it reset at the auth boundary.
 *
 * `remaining` starts at 180 — a leftover from the retired per-user daily cap,
 * kept because it is what the app has always rendered before the first fetch
 * returns. Starting at 0 would make `isExhausted` true on a cold load and flash
 * the "out of credits" state at every user.
 */
const CREDIT_STATE_DEFAULTS = {
  'credit:usedToday': 0,
  'credit:remaining': 180,
  'credit:resetsAt': '',
  'credit:loading': false,
  'credit:error': null,
  'credit:orgExhausted': false,
  'credit:scope': 'workspace',
} as const

/**
 * Reset every `credit:*` key to its initial value.
 *
 * These live in `useState`, which is per-app rather than per-component, so
 * nothing clears them when a session ends. Called from the auth store's
 * `_clearLocalSession()`: without it the next account signed in on the same tab
 * reads the previous workspace's balance until `fetchBalance()` returns — and
 * indefinitely if that request fails.
 */
export function clearCreditState(): void {
  for (const [key, value] of Object.entries(CREDIT_STATE_DEFAULTS)) {
    useState(key, () => value).value = value
  }
}

export const useCreditBalance = () => {
  const { fetchWithRefresh } = useApi()

  // Shared state across all useCreditBalance() instances (Nuxt useState)
  const usedToday = useState<number>('credit:usedToday', () => CREDIT_STATE_DEFAULTS['credit:usedToday'])
  const remaining = useState<number>('credit:remaining', () => CREDIT_STATE_DEFAULTS['credit:remaining'])
  const resetsAt = useState<string>('credit:resetsAt', () => CREDIT_STATE_DEFAULTS['credit:resetsAt'])
  const loading = useState<boolean>('credit:loading', () => CREDIT_STATE_DEFAULTS['credit:loading'])
  const error = useState<string | null>('credit:error', () => CREDIT_STATE_DEFAULTS['credit:error'])
  // Workspace (org) credit pool drained — lets the banner show a
  // workspace-specific message instead of "resets at midnight".
  const orgExhausted = useState<boolean>('credit:orgExhausted', () => CREDIT_STATE_DEFAULTS['credit:orgExhausted'])
  // "workspace" → `remaining` is the org pool total and gates spending.
  // "unlimited" → no org pool; nothing gates the user, so the number is not a
  // real cap and the chat UI hides it.
  const balanceScope = useState<'workspace' | 'unlimited'>('credit:scope', () => CREDIT_STATE_DEFAULTS['credit:scope'])

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
