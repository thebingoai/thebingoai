import type { JobInfo } from '~/types'

export const useJob = (jobId: string) => {
  const api = useApi()

  return useAsyncData<JobInfo>(
    `job-${jobId}`,
    () => api.getJob(jobId),
    {
      server: false,
      lazy: true
    }
  )
}
