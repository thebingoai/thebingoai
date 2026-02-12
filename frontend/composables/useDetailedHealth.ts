import type { DetailedHealthResponse } from '~/types'

export const useDetailedHealth = () => {
  const api = useApi()

  return useAsyncData<DetailedHealthResponse>(
    'detailed-health',
    () => api.getDetailedHealth(),
    {
      server: false,
      lazy: true
    }
  )
}
