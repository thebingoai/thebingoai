import type { useAuthStore } from '~/stores/auth'

export type FetchWithRefresh = (url: string, options?: any) => Promise<any>
export type AuthStore = ReturnType<typeof useAuthStore>
export type RouterLike = ReturnType<typeof useRouter>

export type ApiSliceFactory = (
  fetchWithRefresh: FetchWithRefresh,
  authStore: AuthStore,
  router: RouterLike,
) => unknown

const factories = new Map<string, ApiSliceFactory>()

export interface ApiExtensionRegistry {
  register: (key: string, factory: ApiSliceFactory) => void
  entries: () => Array<[string, ApiSliceFactory]>
}

const registry: ApiExtensionRegistry = {
  register(key, factory) {
    if (factories.has(key)) return
    factories.set(key, factory)
  },
  entries() {
    return [...factories.entries()]
  },
}

export const useApiExtensions = (): ApiExtensionRegistry => registry
