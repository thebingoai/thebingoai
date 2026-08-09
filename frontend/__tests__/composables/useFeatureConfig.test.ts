import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'

// ── Stub Nuxt auto-imports ───────────────────────────────────────────

vi.stubGlobal('ref', ref)
// Keyed store, like Nuxt's useState — callers sharing a key share the ref.
let stateStore: Record<string, any> = {}
vi.stubGlobal('useState', (key: string, init: () => any) => {
  if (!(key in stateStore)) stateStore[key] = ref(init())
  return stateStore[key]
})

// Collect the onMounted callbacks instead of firing them, so a test can mount
// several consumers and then release them all in the same tick — which is what
// a thread full of ChatMessageBubbles actually does.
let mountedCallbacks: Array<() => any> = []
vi.stubGlobal('onMounted', (cb: () => any) => { mountedCallbacks.push(cb) })
vi.stubGlobal('getCurrentInstance', () => ({}))

const mockFetchWithRefresh = vi.fn()
vi.stubGlobal('useApi', () => ({ fetchWithRefresh: mockFetchWithRefresh }))

import { useFeatureConfig } from '~/composables/useFeatureConfig'

const CONFIG = {
  governance_enabled: false,
  chat_export_enabled: false,
  credits_enabled: true,
  admin_enabled: true,
  telegram_enabled: true,
  providers: {
    openai: { configured: true, base_url: 'https://api.openai.com/v1' },
    anthropic: { configured: false, base_url: 'https://api.anthropic.com' },
  },
}

// Mount N consumers, then let every queued onMounted run together.
async function mountConsumers(n: number) {
  const handles = Array.from({ length: n }, () => useFeatureConfig())
  const pending = mountedCallbacks.map(cb => cb())
  mountedCallbacks = []
  await Promise.allSettled(pending)
  return handles
}

describe('useFeatureConfig', () => {
  beforeEach(async () => {
    // Drain any in-flight request left by a prior test before resetting state.
    mockFetchWithRefresh.mockReset()
    mockFetchWithRefresh.mockResolvedValue(CONFIG)
    await mountConsumers(1)
    mockFetchWithRefresh.mockReset()
    mockFetchWithRefresh.mockResolvedValue(CONFIG)
    stateStore = {}
    mountedCallbacks = []
  })

  it('issues one request when many consumers mount in the same tick', async () => {
    // ChatMessageBubble is one instance per message, so this is a long thread.
    const handles = await mountConsumers(50)

    expect(mockFetchWithRefresh).toHaveBeenCalledTimes(1)
    // …and every consumer still sees the resolved config, off the one shared ref.
    // (ref() proxies the object, so compare by value, not identity.)
    expect(handles.every(h => h.config === handles[0].config)).toBe(true)
    handles.forEach(h => expect(h.config.value).toEqual(CONFIG))
  })

  it('does not refetch once config is populated', async () => {
    await mountConsumers(1)
    expect(mockFetchWithRefresh).toHaveBeenCalledTimes(1)

    await mountConsumers(5)
    expect(mockFetchWithRefresh).toHaveBeenCalledTimes(1)
  })

  it('clears the in-flight guard on failure so a later mount retries', async () => {
    mockFetchWithRefresh.mockRejectedValueOnce(new Error('network'))
    await mountConsumers(3)
    // The three racing consumers still only cost one request…
    expect(mockFetchWithRefresh).toHaveBeenCalledTimes(1)
    expect(stateStore['featureConfig'].value).toBeNull()

    // …and the failure didn't wedge the guard.
    mockFetchWithRefresh.mockResolvedValue(CONFIG)
    await mountConsumers(1)
    expect(mockFetchWithRefresh).toHaveBeenCalledTimes(2)
    expect(stateStore['featureConfig'].value).toEqual(CONFIG)
  })

  it('resets loading after the request settles', async () => {
    await mountConsumers(1)
    expect(stateStore['featureConfig:loading'].value).toBe(false)
  })
})
