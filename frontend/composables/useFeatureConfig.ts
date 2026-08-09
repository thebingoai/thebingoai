interface ProviderConfig {
  configured: boolean
  base_url: string
}

interface FeatureConfig {
  governance_enabled: boolean
  chat_export_enabled: boolean
  credits_enabled: boolean
  admin_enabled: boolean
  telegram_enabled: boolean
  providers: {
    openai: ProviderConfig
    anthropic: ProviderConfig
  }
}

// Single-flight guard. `config.value` alone doesn't dedupe: every caller mounts in
// the same tick and they all see null before the first response lands, so each one
// fires its own request. That is per-component, and ChatMessageBubble is one per
// message — a long thread would issue a GET /api/config per bubble.
// Module-level is safe here: ssr is off, so one module instance = one client.
let inflight: Promise<void> | null = null

export const useFeatureConfig = () => {
  const { fetchWithRefresh } = useApi()

  const config = useState<FeatureConfig | null>('featureConfig', () => null)
  const loading = useState<boolean>('featureConfig:loading', () => false)

  const fetch = () => {
    if (config.value) return Promise.resolve()
    if (inflight) return inflight

    loading.value = true
    inflight = fetchWithRefresh<FeatureConfig>('/api/config', { method: 'GET' })
      .then((c) => { config.value = c })
      .finally(() => {
        loading.value = false
        inflight = null   // cleared on failure too, so a later mount can retry
      })
    return inflight
  }

  if (getCurrentInstance()) {
    onMounted(fetch)
  }

  return { config, loading }
}
