import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('~/composables/useSupabase', () => ({
  useSupabase: vi.fn(),
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
vi.stubGlobal('navigateTo', vi.fn())
vi.stubGlobal('ref', (val: any) => {
  const { ref: vueRef } = require('vue')
  return vueRef(val)
})
vi.stubGlobal('computed', (fn: Function) => {
  const { computed: vueComputed } = require('vue')
  return vueComputed(fn)
})

import { useAuthStore } from '~/stores/auth'

vi.stubGlobal('useAuthStore', () => useAuthStore())

import ResetPassword from '~/pages/reset-password.vue'

// ── Stub child components ───────────────────────────────────────────────
const stubs = {
  UiButton: { template: '<button type="submit"><slot /></button>', props: ['loading', 'disabled', 'variant', 'fullWidth'] },
  UiInput: { template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />', props: ['modelValue', 'type', 'label', 'placeholder', 'required'], emits: ['update:modelValue'] },
  NuxtLink: { template: '<a><slot /></a>', props: ['to'] },
}

describe('reset-password page', () => {
  let store: ReturnType<typeof useAuthStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useAuthStore()
    routeQuery.value = {}
    for (const key of Object.keys(storage)) delete storage[key]
    vi.clearAllMocks()
  })

  // ── SSO: shows invalid link when no token ─────────────────────────
  it('shows invalid link message for SSO when no token', () => {
    store.authConfig = { provider: 'sso' }
    routeQuery.value = {}

    const wrapper = mount(ResetPassword, { global: { stubs } })
    expect(wrapper.text()).toContain('Invalid reset link')
  })

  // ── Supabase: shows form even without token ───────────────────────
  it('shows form for Supabase even without token query param', () => {
    store.authConfig = { provider: 'supabase' }
    routeQuery.value = {}

    const wrapper = mount(ResetPassword, { global: { stubs } })
    expect(wrapper.text()).toContain('New Password')
    expect(wrapper.text()).toContain('Reset Password')
    expect(wrapper.text()).not.toContain('Invalid reset link')
  })

  // ── SSO: shows form when token present ────────────────────────────
  it('shows form for SSO when token is present', () => {
    store.authConfig = { provider: 'sso' }
    routeQuery.value = { token: 'reset-token-123' }

    const wrapper = mount(ResetPassword, { global: { stubs } })
    expect(wrapper.text()).toContain('New Password')
    expect(wrapper.text()).toContain('Reset Password')
    expect(wrapper.text()).not.toContain('Invalid reset link')
  })

  // ── Password mismatch ─────────────────────────────────────────────
  it('shows error when passwords do not match', async () => {
    store.authConfig = { provider: 'sso' }
    routeQuery.value = { token: 'reset-token-123' }

    const wrapper = mount(ResetPassword, { global: { stubs } })
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('password1')
    await inputs[1].setValue('password2')

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Passwords do not match')
  })

  // ── Successful reset ──────────────────────────────────────────────
  it('calls resetPassword and shows success on submit', async () => {
    store.authConfig = { provider: 'sso', publishable_key: 'pk_test' }
    routeQuery.value = { token: 'reset-token-123' }

    const resetSpy = vi.spyOn(store, 'resetPassword').mockResolvedValue({ success: true })

    const wrapper = mount(ResetPassword, { global: { stubs } })
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('newpassword123')
    await inputs[1].setValue('newpassword123')

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(resetSpy).toHaveBeenCalledWith('reset-token-123', 'newpassword123')
    expect(wrapper.text()).toContain('Password reset successfully')
  })

  // ── Failed reset ──────────────────────────────────────────────────
  it('shows error on failed reset', async () => {
    store.authConfig = { provider: 'sso', publishable_key: 'pk_test' }
    routeQuery.value = { token: 'expired-token' }

    vi.spyOn(store, 'resetPassword').mockResolvedValue({
      success: false,
      error: 'Token has expired',
    })

    const wrapper = mount(ResetPassword, { global: { stubs } })
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('newpassword123')
    await inputs[1].setValue('newpassword123')

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Token has expired')
  })
})
