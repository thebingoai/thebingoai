import type { ProvidersResponse } from '~/types'

export const useProviders = () => {
  const api = useApi()

  return useAsyncData<ProvidersResponse>(
    'providers',
    () => api.getProviders(),
    {
      server: false,
      lazy: true
    }
  )
}
