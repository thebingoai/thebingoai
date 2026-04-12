// utils/api/adminApi.ts

export interface AdminUser {
  id: string
  email: string
  role: 'admin' | 'user'
  is_active: boolean
  daily_limit: number
  used_today: number
  created_at: string | null
}

export interface AdminUserDetail extends AdminUser {
  daily_totals: { date: string; total: number }[]
}

export interface AdminUsersResponse {
  items: AdminUser[]
  total: number
  page: number
  per_page: number
}

export function createAdminApi(fetchWithRefresh: Function) {
  return {
    async getUsers(params?: {
      search?: string
      role?: string
      status?: string
      page?: number
      per_page?: number
    }): Promise<AdminUsersResponse> {
      const query = new URLSearchParams()
      if (params?.search) query.append('search', params.search)
      if (params?.role) query.append('role', params.role)
      if (params?.status) query.append('status', params.status)
      if (params?.page) query.append('page', String(params.page))
      if (params?.per_page) query.append('per_page', String(params.per_page))
      return fetchWithRefresh(`/api/admin/users?${query.toString()}`, {})
    },

    async getUser(userId: string): Promise<AdminUserDetail> {
      return fetchWithRefresh(`/api/admin/users/${userId}`, {})
    },

    async setRole(userId: string, role: 'admin' | 'user'): Promise<{ user_id: string; role: string }> {
      return fetchWithRefresh(`/api/admin/users/${userId}/role`, {
        method: 'PATCH',
        body: { role },
      })
    },

    async setCredits(userId: string, daily_limit: number): Promise<{ user_id: string; daily_limit: number }> {
      return fetchWithRefresh(`/api/admin/users/${userId}/credits`, {
        method: 'PATCH',
        body: { daily_limit },
      })
    },

    async deactivateUser(userId: string): Promise<{ user_id: string; is_active: boolean }> {
      return fetchWithRefresh(`/api/admin/users/${userId}/deactivate`, {
        method: 'POST',
      })
    },

    async activateUser(userId: string): Promise<{ user_id: string; is_active: boolean }> {
      return fetchWithRefresh(`/api/admin/users/${userId}/activate`, {
        method: 'POST',
      })
    },
  }
}
