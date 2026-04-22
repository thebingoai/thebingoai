interface ProviderConfig {
  configured: boolean
  base_url: string
}

interface FeatureConfig {
  governance_enabled: boolean
  credits_enabled: boolean
  admin_enabled: boolean
  telegram_enabled: boolean
  providers: {
    openai: ProviderConfig
    anthropic: ProviderConfig
  }
}

export const useFeatureConfig = () => {
  const { fetchWithRefresh } = useApi()

  const config = useState<FeatureConfig | null>('featureConfig', () => null)
  const loading = useState<boolean>('featureConfig:loading', () => false)

  const fetch = async () => {
    if (config.value) return
    loading.value = true
    try {
      config.value = await fetchWithRefresh<FeatureConfig>('/api/config', { method: 'GET' })
    } finally {
      loading.value = false
    }
  }

  onMounted(fetch)

  return { config, loading }
}
