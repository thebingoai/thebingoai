import { useAuthStore } from '~/stores/auth'
import { createFetchHelper } from '~/utils/api/fetchHelper'
import { createChatApi } from '~/utils/api/chatApi'
import { createConnectionsApi } from '~/utils/api/connectionsApi'
import { createDashboardsApi } from '~/utils/api/dashboardsApi'
import { createResourcesApi } from '~/utils/api/resourcesApi'
import { createFacebookAdsApi } from '~/utils/api/facebookAdsApi'
import { createAdminApi } from '~/utils/api/adminApi'
import { createTelegramApi } from '~/utils/api/telegramApi'

export const useApi = () => {
  const authStore = useAuthStore()
  const router = useRouter()
  const { fetchWithRefresh } = createFetchHelper(authStore, router)

  const resources = createResourcesApi(fetchWithRefresh, authStore, router)

  return {
    fetchWithRefresh,
    ...resources,
    connections: createConnectionsApi(fetchWithRefresh, authStore, router),
    chat: createChatApi(fetchWithRefresh, authStore, router),
    dashboards: createDashboardsApi(fetchWithRefresh),
    facebookAds: createFacebookAdsApi(fetchWithRefresh),
    admin: createAdminApi(fetchWithRefresh),
    telegram: createTelegramApi(fetchWithRefresh),
  }
}
