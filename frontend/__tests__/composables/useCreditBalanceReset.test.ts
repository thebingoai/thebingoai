import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, computed } from 'vue'

// ── Stub Nuxt auto-imports ───────────────────────────────────────────
//
// `useState` is stubbed KEYED here, unlike useCreditBalance.test.ts which hands
// back a fresh ref per call. The sharing is the whole point: credit state
// outliving a session is only possible because every caller reaches the same
// ref, so a per-call stub cannot reproduce the leak this file guards.

const stateStore = new Map<string, any>()
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('onMounted', vi.fn())
vi.stubGlobal('getCurrentInstance', vi.fn(() => null)) // never auto-fetch on mount
vi.stubGlobal('useState', (key: string, init: () => any) => {
  if (!stateStore.has(key)) stateStore.set(key, ref(init()))
  return stateStore.get(key)
})

const mockFetchWithRefresh = vi.fn()
vi.stubGlobal('useApi', () => ({ fetchWithRefresh: mockFetchWithRefresh }))

import { useCreditBalance, clearCreditState } from '~/composables/useCreditBalance'

const ALICE = {
  used_today: 40,
  remaining: 2525,
  resets_at: '2026-08-07T00:00:00+00:00',
  org_exhausted: false,
  balance_scope: 'workspace',
}

describe('credit state at the auth boundary', () => {
  beforeEach(() => {
    stateStore.clear()
    mockFetchWithRefresh.mockReset()
  })

  it('is shared across instances — which is why a session can leak it', async () => {
    mockFetchWithRefresh.mockResolvedValue(ALICE)
    await useCreditBalance().refresh()

    // A second, independent caller sees the first one's values.
    expect(useCreditBalance().remaining.value).toBe(2525)
    expect(useCreditBalance().usedToday.value).toBe(40)
  })

  it('clearCreditState resets every key it owns', async () => {
    mockFetchWithRefresh.mockResolvedValue({ ...ALICE, org_exhausted: true, balance_scope: 'unlimited' })
    await useCreditBalance().refresh()

    clearCreditState()

    const c = useCreditBalance()
    expect(c.remaining.value).toBe(180)
    expect(c.usedToday.value).toBe(0)
    expect(c.resetsAt.value).toBe('')
    expect(c.orgExhausted.value).toBe(false)
    expect(c.balanceScope.value).toBe('workspace')
    expect(c.error.value).toBeNull()
    expect(c.loading.value).toBe(false)
  })

  it('does not carry one account\'s balance into the next', async () => {
    mockFetchWithRefresh.mockResolvedValue(ALICE)
    await useCreditBalance().refresh()
    expect(useCreditBalance().remaining.value).toBe(2525)

    // …logout…
    clearCreditState()

    // Bob signs in on the same tab. Before his balance arrives he must not be
    // shown Alice's, and `isExhausted` must not fire on the placeholder.
    const bob = useCreditBalance()
    expect(bob.remaining.value).not.toBe(2525)
    expect(bob.isExhausted.value).toBe(false)
  })

  it('leaves no stale error or loading flag for the next session', async () => {
    mockFetchWithRefresh.mockRejectedValue(new Error('network down'))
    await useCreditBalance().refresh()
    expect(useCreditBalance().error.value).toBe('network down')

    clearCreditState()
    expect(useCreditBalance().error.value).toBeNull()
  })

  it('is safe to call before any credit state exists', () => {
    // Logout can run on a session that never loaded a balance.
    expect(() => clearCreditState()).not.toThrow()
    expect(useCreditBalance().remaining.value).toBe(180)
  })
})
