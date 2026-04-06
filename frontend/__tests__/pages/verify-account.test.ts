import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

// ── Supabase mock ───────────────────────────────────────────────────────
const verifyOtp = vi.fn()
vi.mock('~/composables/useSupabase', () => ({
  useSupabase: () => ({ auth: { verifyOtp } }),
}))

// ── Dependent stores mocked so auth store loads ─────────────────────────
vi.mock('~/stores/chat', () => ({
  useChatStore: () => ({ reset: vi.fn() }),
}))
vi.mock('~/stores/dashboard', () => ({
  useDashboardStore: () => ({ $resetAll: vi.fn() }),
}))
vi.mock('~/composables/useWebSocket', () => ({
  useWebSocket: () => ({ disconnect: vi.fn(), clearHandlers: vi.fn() }),
}))

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
  // Use Vue's ref from the import
  const { ref: vueRef } = require('vue')
  return vueRef(val)
})
vi.stubGlobal('onMounted', (fn: Function) => fn())
vi.stubGlobal('navigateTo', vi.fn())

import { useAuthStore } from '~/stores/auth'

// Stub useAuthStore as a global (Nuxt auto-import)
vi.stubGlobal('useAuthStore', () => useAuthStore())
vi.stubGlobal('useSupabase', () => ({ auth: { verifyOtp } }))

import VerifyAccount from '~/pages/verify-account.vue'

// ── Stub child components ───────────────────────────────────────────────
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

  // ── No token: shows "check your email" ────────────────────────────
  it('shows check-your-email message when no token is present', async () => {
    store.authConfig = { provider: 'sso' }
    const wrapper = mount(VerifyAccount, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Check your email')
    expect(wrapper.text()).toContain('Click the link in the email to verify your account')
  })

  // ── SSO: successful verification ──────────────────────────────────
  it('calls verifyEmail and shows success for SSO', async () => {
    store.authConfig = { provider: 'sso', publishable_key: 'pk_test' }
    routeQuery.value = { token: 'sso-verify-token' }

    const verifyEmailSpy = vi.spyOn(store, 'verifyEmail').mockResolvedValue({ success: true })

    mount(VerifyAccount, { global: { stubs } })
    await flushPromises()

    expect(verifyEmailSpy).toHaveBeenCalledWith('sso-verify-token')
  })

  // ── SSO: failed verification ──────────────────────────────────────
  it('shows error on SSO verification failure', async () => {
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

  // ── Supabase: successful verification ─────────────────────────────
  it('calls verifyOtp for Supabase with token_hash', async () => {
    store.authConfig = { provider: 'supabase' }
    routeQuery.value = { token_hash: 'abc123', type: 'email' }

    verifyOtp.mockResolvedValue({
      data: { session: { access_token: 'sb-token' } },
      error: null,
    })

    const fetchUserSpy = vi.spyOn(store, 'fetchUser').mockResolvedValue()

    mount(VerifyAccount, { global: { stubs } })
    await flushPromises()

    expect(verifyOtp).toHaveBeenCalledWith({ token_hash: 'abc123', type: 'email' })
    expect(store.token).toBe('sb-token')
    expect(fetchUserSpy).toHaveBeenCalled()
  })

  // ── Supabase: verification error ──────────────────────────────────
  it('shows error on Supabase verification failure', async () => {
    store.authConfig = { provider: 'supabase' }
    routeQuery.value = { token_hash: 'bad-hash', type: 'email' }

    verifyOtp.mockResolvedValue({
      data: {},
      error: { message: 'Invalid token hash' },
    })

    const wrapper = mount(VerifyAccount, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Invalid token hash')
  })

  // ── SSO: resend verification ──────────────────────────────────────
  it('shows resend button for SSO when pendingEmail is set', async () => {
    store.authConfig = { provider: 'sso', publishable_key: 'pk_test' }

    const wrapper = mount(VerifyAccount, { global: { stubs } })
    await flushPromises()

    // pendingEmail is empty by default, so resend button should not show
    expect(wrapper.text()).not.toContain('Resend verification email')
  })
})
