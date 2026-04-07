import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

// ── Dependent stores mocked so auth store loads ─────────────────────────
vi.stubGlobal('useChatStore', () => ({ reset: vi.fn() }))
vi.stubGlobal('useDashboardStore', () => ({ $resetAll: vi.fn() }))
vi.stubGlobal('useWebSocket', () => ({ disconnect: vi.fn(), clearHandlers: vi.fn() }))

vi.stubGlobal('$fetch', vi.fn())
;(globalThis as any).process = { ...process, client: true }
const storage: Record<string, string> = {}
vi.stubGlobal('localStorage', {
  getItem: vi.fn((key: string) => storage[key] ?? null),
  setItem: vi.fn((key: string, val: string) => { storage[key] = val }),
  removeItem: vi.fn((key: string) => { delete storage[key] }),
})

// ── Nuxt auto-import stubs ──────────────────────────────────────────────
const routeQuery = { value: {} as Record<string, string> }
const routerPush = vi.fn()
vi.stubGlobal('definePageMeta', vi.fn())
vi.stubGlobal('useRouter', () => ({ push: routerPush }))
vi.stubGlobal('useRoute', () => ({ query: routeQuery.value }))
vi.stubGlobal('ref', (val: any) => {
  const { ref: vueRef } = require('vue')
  return vueRef(val)
})
vi.stubGlobal('onMounted', (fn: Function) => fn())
vi.stubGlobal('navigateTo', vi.fn())

import { useAuthStore } from '~/stores/auth'

vi.stubGlobal('useAuthStore', () => useAuthStore())

import VerifyAccount from '~/pages/verify-account.vue'

const stubs = {
  UiButton: { template: '<button><slot /></button>', props: ['loading', 'disabled', 'variant', 'fullWidth'] },
  NuxtLink: { template: '<a><slot /></a>', props: ['to'] },
}

describe('verify-account page', () => {
  let store: ReturnType<typeof useAuthStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useAuthStore()
    routeQuery.value = {}
    for (const key of Object.keys(storage)) delete storage[key]
    vi.clearAllMocks()
  })

  it('shows check-your-email message when no token is present', async () => {
    store.authConfig = { provider: 'sso' }
    const wrapper = mount(VerifyAccount, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Check your email')
    expect(wrapper.text()).toContain('Click the link in the email to verify your account')
  })

  it('calls verifyEmail and shows success for SSO token', async () => {
    store.authConfig = { provider: 'sso', publishable_key: 'pk_test' }
    routeQuery.value = { token: 'sso-verify-token' }

    const verifyEmailSpy = vi.spyOn(store, 'verifyEmail').mockResolvedValue({ success: true })

    mount(VerifyAccount, { global: { stubs } })
    await flushPromises()

    expect(verifyEmailSpy).toHaveBeenCalledWith('sso-verify-token')
  })

  it('shows error on verification failure', async () => {
    store.authConfig = { provider: 'sso', publishable_key: 'pk_test' }
    routeQuery.value = { token: 'bad-token' }

    vi.spyOn(store, 'verifyEmail').mockResolvedValue({
      success: false,
      error: 'Token expired',
    })

    const wrapper = mount(VerifyAccount, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Token expired')
  })

  it('does not show resend button when pendingEmail is empty', async () => {
    store.authConfig = { provider: 'sso', publishable_key: 'pk_test' }

    const wrapper = mount(VerifyAccount, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).not.toContain('Resend verification email')
  })
})
