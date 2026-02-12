import type { StatusResponse } from '~/types'

export const useStatus = () => {
  const api = useApi()

  return useAsyncData<StatusResponse>(
    'status',
    () => api.getStatus(),
    {
      server: false,
      lazy: true
    }
  )
}
