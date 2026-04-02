export function createFetchHelper(authStore: any, router: any) {
  const getHeaders = () => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
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
          ...getHeaders(),
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
              ...getHeaders(),
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
