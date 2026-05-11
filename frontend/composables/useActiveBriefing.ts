// Shared state between InfoPanelBriefings and chat page for inline briefing view
export function useActiveBriefing() {
  const route = useRoute()
  const router = useRouter()
  const state = useState<number | null>('active-briefing-id', () => null)

  // Sync from URL on mount
  const id = computed<number | null>(() => {
    // Prefer the state; fall back to query param
    const fromRoute = route.query.briefing
    if (fromRoute) {
      const parsed = parseInt(fromRoute as string, 10)
      return isNaN(parsed) ? null : parsed
    }
    return null
  })

  // Keep state in sync with computed
  watch(id, (val) => { state.value = val })

  function open(id: number) {
    state.value = id
    router.replace({ path: '/chat', query: { ...route.query, briefing: String(id) } })
  }

  function close() {
    state.value = null
    router.replace({ path: '/chat', query: { ...route.query, briefing: undefined } })
  }

  return { id, open, close }
}
