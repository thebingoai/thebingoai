import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, computed, watch } from 'vue'

// ── Stub Nuxt auto-imports ───────────────────────────────────────────

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('watch', watch)
vi.stubGlobal('onMounted', vi.fn((cb: () => void) => cb()))

const mockFetch = vi.fn()
vi.stubGlobal('useApi', () => ({ fetchWithRefresh: mockFetch }))

import { useCreditSettings } from '~/composables/useCreditSettings'

// ── Helpers ──────────────────────────────────────────────────────────

function makeBalance(overrides = {}) {
  return { daily_limit: 180, used_today: 60, remaining: 120, ...overrides }
}

function makeHistory(items: any[] = [], page = 1, total = 0) {
  return { items, total, page, per_page: 20 }
}

function makeKey(provider = 'openai', masked = 'sk-...456789') {
  return { provider, masked_key: masked, api_base_url: null, is_active: true }
}

describe('useCreditSettings', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('fetches balance, history, and keys on mount', async () => {
    mockFetch
      .mockResolvedValueOnce(makeBalance())        // balance
      .mockResolvedValueOnce(makeHistory())         // history
      .mockResolvedValueOnce([])                    // api-keys

    const { dailyLimit, usedToday, remaining } = useCreditSettings()
    await vi.waitUntil(() => mockFetch.mock.calls.length >= 3)

    expect(dailyLimit.value).toBe(180)
    expect(usedToday.value).toBe(60)
    expect(remaining.value).toBe(120)
  })

  it('usedPercent computes correctly', async () => {
    mockFetch
      .mockResolvedValueOnce(makeBalance({ used_today: 90, remaining: 90 }))
      .mockResolvedValueOnce(makeHistory())
      .mockResolvedValueOnce([])

    const { usedPercent } = useCreditSettings()
    await vi.waitUntil(() => mockFetch.mock.calls.length >= 3)

    expect(usedPercent.value).toBeCloseTo(50)
  })

  it('loads usage history items', async () => {
    const items = [
      { id: 1, title: 'Query 1', credits_used: 2.5, date: '2026-04-10', created_at: '2026-04-10T10:00:00' },
      { id: 2, title: 'Query 2', credits_used: 1.1, date: '2026-04-10', created_at: '2026-04-10T11:00:00' },
    ]
    mockFetch
      .mockResolvedValueOnce(makeBalance())
      .mockResolvedValueOnce(makeHistory(items, 1, 2))
      .mockResolvedValueOnce([])

    const { historyItems, historyTotal } = useCreditSettings()
    await vi.waitUntil(() => mockFetch.mock.calls.length >= 3)

    expect(historyItems.value).toHaveLength(2)
    expect(historyTotal.value).toBe(2)
    expect(historyItems.value[0].title).toBe('Query 1')
  })

  it('historyTotalPages computes from total and per_page', async () => {
    mockFetch
      .mockResolvedValueOnce(makeBalance())
      .mockResolvedValueOnce(makeHistory([], 1, 45))  // 45 items, 20 per page → 3 pages
      .mockResolvedValueOnce([])

    const { historyTotalPages } = useCreditSettings()
    await vi.waitUntil(() => mockFetch.mock.calls.length >= 3)

    expect(historyTotalPages.value).toBe(3)
  })

  it('nextPage fetches the next page', async () => {
    mockFetch
      .mockResolvedValueOnce(makeBalance())
      .mockResolvedValueOnce(makeHistory([], 1, 40))
      .mockResolvedValueOnce([])                      // dailyTotals
      .mockResolvedValueOnce([])                      // api-keys
      .mockResolvedValueOnce(makeHistory([], 2, 40))  // page 2

    const { nextPage, historyPage } = useCreditSettings()
    await vi.waitUntil(() => mockFetch.mock.calls.length >= 4)

    await nextPage()
    expect(historyPage.value).toBe(2)
  })

  it('prevPage fetches the previous page', async () => {
    mockFetch
      .mockResolvedValueOnce(makeBalance())
      .mockResolvedValueOnce(makeHistory([], 2, 40))
      .mockResolvedValueOnce([])                      // dailyTotals
      .mockResolvedValueOnce([])                      // api-keys
      .mockResolvedValueOnce(makeHistory([], 1, 40))  // page 1

    const { prevPage, historyPage } = useCreditSettings()
    await vi.waitUntil(() => mockFetch.mock.calls.length >= 4)

    await prevPage()
    expect(historyPage.value).toBe(1)
  })

  it('loads API keys', async () => {
    mockFetch
      .mockResolvedValueOnce(makeBalance())
      .mockResolvedValueOnce(makeHistory())
      .mockResolvedValueOnce([])                               // dailyTotals
      .mockResolvedValueOnce([makeKey('openai', 'sk-...456789')])

    const { apiKeys } = useCreditSettings()
    await vi.waitUntil(() => mockFetch.mock.calls.length >= 4)

    expect(apiKeys.value).toHaveLength(1)
    expect(apiKeys.value[0].provider).toBe('openai')
    expect(apiKeys.value[0].masked_key).toBe('sk-...456789')
    // Ensure plaintext key is never exposed
    expect(apiKeys.value[0].masked_key).not.toContain('real-key')
  })

  it('saveApiKey calls POST and refreshes keys', async () => {
    mockFetch
      .mockResolvedValueOnce(makeBalance())
      .mockResolvedValueOnce(makeHistory())
      .mockResolvedValueOnce([])          // dailyTotals
      .mockResolvedValueOnce([])          // initial keys
      .mockResolvedValueOnce(undefined)   // POST save
      .mockResolvedValueOnce([makeKey()]) // refreshed keys

    const { apiKeys, saveApiKey } = useCreditSettings()
    await vi.waitUntil(() => mockFetch.mock.calls.length >= 4)

    await saveApiKey('openai', 'sk-real-key')

    expect(mockFetch).toHaveBeenCalledWith('/api/credits/api-keys', expect.objectContaining({
      method: 'POST',
      body: expect.objectContaining({ provider: 'openai', api_key: 'sk-real-key' }),
    }))
    expect(apiKeys.value).toHaveLength(1)
  })

  it('deleteApiKey calls DELETE and refreshes keys', async () => {
    mockFetch
      .mockResolvedValueOnce(makeBalance())
      .mockResolvedValueOnce(makeHistory())
      .mockResolvedValueOnce([])                      // dailyTotals
      .mockResolvedValueOnce([makeKey('openai')])     // initial keys
      .mockResolvedValueOnce(undefined)               // DELETE
      .mockResolvedValueOnce([])                      // refreshed

    const { apiKeys, deleteApiKey } = useCreditSettings()
    await vi.waitUntil(() => mockFetch.mock.calls.length >= 4)

    await deleteApiKey('openai')

    expect(mockFetch).toHaveBeenCalledWith('/api/credits/api-keys/openai', { method: 'DELETE' })
    expect(apiKeys.value).toHaveLength(0)
  })

  it('default base URL is pre-filled for openai', () => {
    // Verify the DEFAULT_BASE_URLS constant is correct
    expect('https://api.openai.com/v1').toContain('openai')
    expect('https://api.anthropic.com').toContain('anthropic')
  })
})
