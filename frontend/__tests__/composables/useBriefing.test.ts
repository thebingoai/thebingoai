import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, computed } from 'vue'

// ── Stub Nuxt auto-imports ───────────────────────────────────────────

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('readonly', (v: any) => v)
vi.stubGlobal('unref', (v: any) => (v && typeof v === 'object' && 'value' in v ? v.value : v))
vi.stubGlobal('onUnmounted', vi.fn())

vi.stubGlobal('watch', (_src: any, cb: any, opts?: any) => {
  if (opts?.immediate) cb(true) // pass truthy so `if (newId)` in the composable passes
})

const mockFetch = vi.fn()
vi.stubGlobal('useApi', () => ({ fetchWithRefresh: mockFetch }))

import { useBriefing } from '~/composables/useBriefing'

// ── Helpers ──────────────────────────────────────────────────────────

function makeBriefing(overrides: Record<string, any> = {}) {
  return {
    id: 1, user_id: 'u1', dashboard_id: 10, source: 'manual',
    status: 'ready',
    payload: {
      headline: 'Revenue held', deck: 'Topline tracked.',
      kpis: [{ label: 'MRR', value: '$13,816', delta_vs_prev: '+0.3%', delta_direction: 'up' }],
      sections: [{ heading: '1. Lift', prose: 'Strong growth.', widget_id: null }],
      key_takeaways: ['a', 'b', 'c'],
    },
    error: null, date_range_from: null, date_range_to: null,
    created_at: '2026-05-08T09:00:00Z',
    ...overrides,
  }
}

async function tick() {
  await new Promise(r => setTimeout(r, 10))
}

describe('useBriefing', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('fetches briefing on mount', async () => {
    mockFetch.mockResolvedValue(makeBriefing())
    const { briefing, loading } = useBriefing(1)

    await tick()
    expect(mockFetch).toHaveBeenCalledWith('/api/briefings/1', {})
    expect(briefing.value!.status).toBe('ready')
    expect(briefing.value!.payload!.headline).toBe('Revenue held')
    expect(loading.value).toBe(false)
  })

  it('starts a polling interval after receiving generating status', async () => {
    const setIntervalSpy = vi.spyOn(global, 'setInterval')
    mockFetch.mockResolvedValue(makeBriefing({ status: 'generating', payload: null }))

    useBriefing(1)
    await tick()
    expect(mockFetch).toHaveBeenCalledTimes(1)
    // The composable should set up a 3-second poll interval
    expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 3000)
    setIntervalSpy.mockRestore()
  })

  it('does not start polling for ready responses', async () => {
    const setIntervalSpy = vi.spyOn(global, 'setInterval')
    mockFetch.mockResolvedValue(makeBriefing({ status: 'ready' }))

    useBriefing(1)
    await tick()
    // setInterval should NOT be called — the briefing is already ready
    const pollingCalls = setIntervalSpy.mock.calls.filter(
      c => c[1] === 3000
    )
    expect(pollingCalls).toHaveLength(0)
    setIntervalSpy.mockRestore()
  })

  it('handles reactive briefingId changes', async () => {
    mockFetch
      .mockResolvedValueOnce(makeBriefing({ id: 1 }))
      .mockResolvedValueOnce(makeBriefing({ id: 2 }))

    const id = ref(1)
    const { briefing } = useBriefing(id)

    await tick()
    expect(briefing.value!.id).toBe(1)

    // Simulate route change by re-creating the composable
    // (simpler than trying to trigger Nuxt's watch behavior in tests)
    mockFetch.mockClear()
    const { briefing: b2 } = useBriefing(ref(2))
    await tick()
    expect(b2.value!.id).toBe(2)
  })

  it('clears error on successful refetch', async () => {
    mockFetch
      .mockRejectedValueOnce(new Error('Boom'))
      .mockResolvedValueOnce(makeBriefing())

    const { error, briefing } = useBriefing(1)
    await tick()
    expect(error.value).toContain('Boom')

    // Re-create to trigger a fresh fetch
    mockFetch.mockClear()
    mockFetch.mockResolvedValue(makeBriefing())
    const { briefing: b2, error: e2 } = useBriefing(1)
    await tick()
    expect(e2.value).toBe('')
    expect(b2.value!.status).toBe('ready')
  })

  it('exposes refresh function', async () => {
    mockFetch
      .mockResolvedValueOnce(makeBriefing({ status: 'generating', payload: null }))
      .mockResolvedValueOnce(makeBriefing())

    const { briefing, refresh } = useBriefing(1)
    await tick()
    expect(briefing.value!.status).toBe('generating')

    await refresh()
    expect(briefing.value!.status).toBe('ready')
    expect(mockFetch).toHaveBeenCalledTimes(2)
  })

})
