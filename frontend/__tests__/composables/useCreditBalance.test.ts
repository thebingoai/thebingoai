import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, computed } from 'vue'

// ── Stub Nuxt auto-imports ───────────────────────────────────────────

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('onMounted', vi.fn((cb: () => void) => cb())) // call immediately
vi.stubGlobal('useState', (_key: string, init: () => any) => ref(init()))
// Truthy by default = "inside a component setup" → the onMounted guard fires.
// Individual tests override to null to simulate a non-setup caller.
const mockGetCurrentInstance = vi.fn<() => any>(() => ({}))
vi.stubGlobal('getCurrentInstance', mockGetCurrentInstance)

const mockFetchWithRefresh = vi.fn()
vi.stubGlobal('useApi', () => ({
  fetchWithRefresh: mockFetchWithRefresh,
}))

import { useCreditBalance } from '~/composables/useCreditBalance'

// ── Helpers ──────────────────────────────────────────────────────────

function makeBalance(overrides = {}) {
  return {
    used_today: 0,
    remaining: 180,
    resets_at: '2026-04-11T00:00:00+00:00',
    ...overrides,
  }
}

describe('useCreditBalance', () => {
  beforeEach(() => {
    mockFetchWithRefresh.mockReset()
    mockGetCurrentInstance.mockReturnValue({}) // default: inside setup
  })

  it('fetches balance on mount and exposes reactive fields', async () => {
    mockFetchWithRefresh.mockResolvedValue(makeBalance({ used_today: 40, remaining: 140 }))

    const { usedToday, remaining } = useCreditBalance()
    await vi.waitUntil(() => mockFetchWithRefresh.mock.calls.length > 0)

    expect(mockFetchWithRefresh).toHaveBeenCalledWith('/api/credits/balance', { method: 'GET' })
    expect(usedToday.value).toBe(40)
    expect(remaining.value).toBe(140)
  })

  it('isExhausted is false when remaining > 0', async () => {
    mockFetchWithRefresh.mockResolvedValue(makeBalance({ remaining: 50 }))

    const { isExhausted } = useCreditBalance()
    await vi.waitUntil(() => mockFetchWithRefresh.mock.calls.length > 0)

    expect(isExhausted.value).toBe(false)
  })

  it('isExhausted is true when remaining === 0', async () => {
    mockFetchWithRefresh.mockResolvedValue(makeBalance({ remaining: 0 }))

    const { isExhausted } = useCreditBalance()
    await vi.waitUntil(() => mockFetchWithRefresh.mock.calls.length > 0)

    expect(isExhausted.value).toBe(true)
  })

  it('isExhausted is true when remaining < 0', async () => {
    mockFetchWithRefresh.mockResolvedValue(makeBalance({ remaining: -5 }))

    const { isExhausted } = useCreditBalance()
    await vi.waitUntil(() => mockFetchWithRefresh.mock.calls.length > 0)

    expect(isExhausted.value).toBe(true)
  })

  it('refresh() re-fetches the balance', async () => {
    mockFetchWithRefresh
      .mockResolvedValueOnce(makeBalance({ remaining: 100 }))
      .mockResolvedValueOnce(makeBalance({ remaining: 90 }))

    const { remaining, refresh } = useCreditBalance()
    await vi.waitUntil(() => mockFetchWithRefresh.mock.calls.length >= 1)
    expect(remaining.value).toBe(100)

    await refresh()
    expect(remaining.value).toBe(90)
    expect(mockFetchWithRefresh).toHaveBeenCalledTimes(2)
  })

  it('sets error on fetch failure', async () => {
    mockFetchWithRefresh.mockRejectedValue(new Error('Network error'))

    const { error } = useCreditBalance()
    await vi.waitUntil(() => mockFetchWithRefresh.mock.calls.length > 0)

    expect(error.value).toContain('Network error')
  })

  it('loading is false after fetch completes', async () => {
    mockFetchWithRefresh.mockResolvedValue(makeBalance())

    const { loading } = useCreditBalance()
    await vi.waitUntil(() => mockFetchWithRefresh.mock.calls.length > 0)

    expect(loading.value).toBe(false)
  })

  it('does not auto-fetch on mount when called outside a component setup', async () => {
    // getCurrentInstance() === null → the onMounted guard must skip registration
    // (callers grabbing only `refresh`, e.g. useChatStreaming/useBriefing, run
    // outside setup where onMounted would warn with no instance to bind to).
    mockGetCurrentInstance.mockReturnValue(null)
    mockFetchWithRefresh.mockResolvedValue(makeBalance())

    const { refresh } = useCreditBalance()
    expect(mockFetchWithRefresh).not.toHaveBeenCalled()

    // …but on-demand refresh still works.
    await refresh()
    expect(mockFetchWithRefresh).toHaveBeenCalledTimes(1)
  })
})
