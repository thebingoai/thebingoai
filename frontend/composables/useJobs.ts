import type { JobListResponse } from '~/types'

export const useJobs = (namespace?: string, limit?: number) => {
  const api = useApi()

  return useAsyncData<JobListResponse>(
    `jobs-${namespace || 'all'}`,
    () => api.getJobs(namespace, limit),
    {
      server: false,
      lazy: true
    }
  )
}
