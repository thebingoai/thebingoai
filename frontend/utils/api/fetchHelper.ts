export function createFetchHelper(authStore: any, router: any) {
  const getHeaders = (body?: any) => {
    const headers: Record<string, string> = {}

    // Let the browser set its own multipart/form-data boundary for FormData uploads
    if (!(body instanceof FormData)) {
      headers['Content-Type'] = 'application/json'
    }

    if (authStore.token) {
      headers['Authorization'] = `Bearer ${authStore.token}`
    }

    return headers
  }

  const fetchWithRefresh = async <T>(url: string, options: Parameters<typeof $fetch>[1] = {}): Promise<T> => {
    try {
      return await $fetch<T>(url, {
        ...options,
        headers: {
          ...getHeaders(options.body),
          ...(options.headers as Record<string, string> || {}),
        },
      })
    } catch (error: any) {
      if (error?.statusCode === 401 || error?.status === 401) {
        const refreshed = await authStore.refreshAccessToken()
        if (refreshed) {
          // Retry with new token
          return await $fetch<T>(url, {
            ...options,
            headers: {
              ...getHeaders(options.body),
              ...(options.headers as Record<string, string> || {}),
            },
          })
        } else {
          // Refresh failed - logout and redirect
          await authStore.logout()
          await router.push('/login')
          throw error
        }
      }
      throw error
    }
  }

  return { fetchWithRefresh, getHeaders }
}
