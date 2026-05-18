import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, computed } from 'vue'

// ── Stub Nuxt auto-imports ───────────────────────────────────────────
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)

// useState in Nuxt returns a shared, named ref. For tests we route every
// distinct key to its own shared ref so the composable behaves the same
// across multiple invocations within one test (i.e. shared cache).
const stateStore = new Map<string, any>()
vi.stubGlobal('useState', (key: string, init: () => any) => {
  if (!stateStore.has(key)) stateStore.set(key, ref(init()))
  return stateStore.get(key)
})

const mockFetch = vi.fn()
vi.stubGlobal('useApi', () => ({ fetchWithRefresh: mockFetch }))

import { useBriefingsList } from '~/composables/useBriefingsList'

function makeBriefing(overrides: Record<string, any> = {}) {
  return {
    id: 1, user_id: 'u1', dashboard_id: 10, dashboard_name: 'Sales',
    source: 'manual', status: 'ready', payload: { headline: 'h', deck: 'd', kpis: [], sections: [], key_takeaways: [] },
    error: null, date_range_from: null, date_range_to: null,
    created_at: '2026-05-17T10:00:00Z', ...overrides,
  }
}

async function tick() {
  await new Promise(r => setTimeout(r, 0))
}

describe('useBriefingsList', () => {
  beforeEach(() => {
    mockFetch.mockReset()
    stateStore.clear()
  })

  it('starts empty and unloaded', () => {
    const { briefings, loaded, loading } = useBriefingsList()
    expect(briefings.value).toEqual([])
    expect(loaded.value).toBe(false)
    expect(loading.value).toBe(false)
  })

  it('ensure() fetches when not loaded', async () => {
    mockFetch.mockResolvedValue([makeBriefing()])
    const { briefings, loaded, ensure } = useBriefingsList()
    ensure()
    await tick(); await tick()
    expect(mockFetch).toHaveBeenCalledWith('/api/briefings?limit=50', { method: 'GET' })
    expect(loaded.value).toBe(true)
    expect(briefings.value).toHaveLength(1)
  })

  it('ensure() is a no-op once loaded', async () => {
    mockFetch.mockResolvedValue([makeBriefing()])
    const { ensure } = useBriefingsList()
    ensure()
    await tick(); await tick()
    expect(mockFetch).toHaveBeenCalledTimes(1)

    ensure()
    await tick()
    expect(mockFetch).toHaveBeenCalledTimes(1)
  })

  it('refresh() always fetches and replaces list', async () => {
    mockFetch
      .mockResolvedValueOnce([makeBriefing({ id: 1 })])
      .mockResolvedValueOnce([makeBriefing({ id: 2 }), makeBriefing({ id: 3 })])

    const { briefings, refresh } = useBriefingsList()
    await refresh()
    expect(briefings.value).toHaveLength(1)
    await refresh()
    expect(briefings.value).toHaveLength(2)
    expect(briefings.value[0].id).toBe(2)
  })

  it('coalesces overlapping refresh calls into one fetch', async () => {
    let resolveFetch!: (v: any) => void
    mockFetch.mockReturnValue(new Promise(r => { resolveFetch = r }))

    const { refresh } = useBriefingsList()
    const p1 = refresh()
    const p2 = refresh()
    const p3 = refresh()

    resolveFetch([makeBriefing()])
    await Promise.all([p1, p2, p3])

    expect(mockFetch).toHaveBeenCalledTimes(1)
  })

  it('captures error message but keeps loaded=false', async () => {
    mockFetch.mockRejectedValue(new Error('Network down'))
    const { error, loaded, refresh } = useBriefingsList()
    await refresh()
    expect(error.value).toBe('Network down')
    expect(loaded.value).toBe(false)
  })

  it('shares cached state across calls', async () => {
    mockFetch.mockResolvedValue([makeBriefing()])
    const a = useBriefingsList()
    await a.refresh()
    expect(a.briefings.value).toHaveLength(1)

    // Fresh composable invocation should see the same cached list
    // and NOT trigger a new fetch via ensure().
    mockFetch.mockClear()
    const b = useBriefingsList()
    expect(b.loaded.value).toBe(true)
    expect(b.briefings.value).toHaveLength(1)
    b.ensure()
    await tick()
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('invalidate() forces ensure() to refetch', async () => {
    mockFetch.mockResolvedValue([makeBriefing()])
    const { ensure, invalidate, loaded } = useBriefingsList()
    ensure()
    await tick(); await tick()
    expect(loaded.value).toBe(true)
    expect(mockFetch).toHaveBeenCalledTimes(1)

    invalidate()
    expect(loaded.value).toBe(false)
    ensure()
    await tick(); await tick()
    expect(mockFetch).toHaveBeenCalledTimes(2)
  })
})
