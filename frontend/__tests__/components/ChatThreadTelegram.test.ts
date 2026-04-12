import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, computed } from 'vue'

// ── Nuxt auto-import stubs ──────────────────────────────────────────────
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('nextTick', () => Promise.resolve())
vi.stubGlobal('watch', vi.fn())
vi.stubGlobal('defineEmits', vi.fn())

const routerPush = vi.fn()
vi.stubGlobal('useRouter', () => ({ push: routerPush }))

const mockGetStatus = vi.fn()
vi.stubGlobal('useApi', () => ({
  telegram: { getStatus: mockGetStatus },
}))

let mockConversationType = 'permanent'
let mockCurrentThreadId = 'thread-123'
vi.stubGlobal('useChatStore', () => ({
  currentConversation: { type: mockConversationType, title: 'Bingo AI' },
  currentThreadId: mockCurrentThreadId,
  infoPanelOpen: false,
  messages: [],
  isStreaming: false,
  toggleInfoPanel: vi.fn(),
  permanentConversation: { title: 'Bingo AI' },
}))

vi.stubGlobal('useChat', () => ({
  renameConversation: vi.fn(),
}))

let mockTelegramEnabled = true
vi.stubGlobal('useFeatureConfig', () => ({
  config: ref(mockTelegramEnabled ? { telegram_enabled: true } : { telegram_enabled: false }),
}))

// onMounted is called during component setup — invoke the callback immediately
vi.stubGlobal('onMounted', vi.fn((cb: () => void) => cb()))

import ChatThread from '~/components/chat/ChatThread.vue'

const stubs = {
  ChatMessageBubble: { template: '<div />' },
}

const makeChatStore = (type = 'permanent') => ({
  currentConversation: { type, title: 'Bingo AI' },
  currentThreadId: 'thread-123',
  infoPanelOpen: false,
  messages: [],
  isStreaming: false,
  toggleInfoPanel: vi.fn(),
  permanentConversation: type === 'permanent' ? { title: 'Bingo AI' } : null,
})

describe('ChatThread — Telegram icon', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('useChatStore', () => makeChatStore('permanent'))
    vi.stubGlobal('useFeatureConfig', () => ({
      config: ref({ telegram_enabled: true }),
    }))
  })

  it('shows telegram icon on permanent chat when plugin is enabled', async () => {
    mockGetStatus.mockResolvedValue({ connected: false, bot_username: null, is_active: false })
    const wrapper = mount(ChatThread, { global: { stubs } })
    await flushPromises()

    const telegramBtn = wrapper.find('[title="Connect Telegram"]')
    expect(telegramBtn.exists()).toBe(true)
  })

  it('hides telegram icon on non-permanent chat', async () => {
    vi.stubGlobal('useChatStore', () => makeChatStore('task'))

    mockGetStatus.mockResolvedValue({ connected: false, bot_username: null, is_active: false })
    const wrapper = mount(ChatThread, { global: { stubs } })
    await flushPromises()

    const telegramBtnConnected = wrapper.find('[title="Telegram connected"]')
    const telegramBtnDisconnected = wrapper.find('[title="Connect Telegram"]')
    expect(telegramBtnConnected.exists()).toBe(false)
    expect(telegramBtnDisconnected.exists()).toBe(false)
  })

  it('hides telegram icon when plugin is not enabled', async () => {
    vi.stubGlobal('useFeatureConfig', () => ({
      config: ref({ telegram_enabled: false }),
    }))

    mockGetStatus.mockResolvedValue({ connected: false, bot_username: null, is_active: false })
    const wrapper = mount(ChatThread, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('[title="Connect Telegram"]').exists()).toBe(false)
    expect(wrapper.find('[title="Telegram connected"]').exists()).toBe(false)
  })

  it('shows gray icon when not connected', async () => {
    mockGetStatus.mockResolvedValue({ connected: false, bot_username: null, is_active: false })
    const wrapper = mount(ChatThread, { global: { stubs } })
    await flushPromises()

    const btn = wrapper.find('[title="Connect Telegram"]')
    expect(btn.exists()).toBe(true)
    expect(btn.classes()).toContain('text-gray-400')
  })

  it('shows green icon when connected', async () => {
    mockGetStatus.mockResolvedValue({ connected: true, bot_username: 'mybot', is_active: true })
    const wrapper = mount(ChatThread, { global: { stubs } })
    await flushPromises()

    const btn = wrapper.find('[title="Telegram connected"]')
    expect(btn.exists()).toBe(true)
    expect(btn.classes()).toContain('text-green-500')
  })

  it('navigates to /settings?tab=channels on click', async () => {
    mockGetStatus.mockResolvedValue({ connected: false, bot_username: null, is_active: false })
    const wrapper = mount(ChatThread, { global: { stubs } })
    await flushPromises()

    const btn = wrapper.find('[title="Connect Telegram"]')
    await btn.trigger('click')

    expect(routerPush).toHaveBeenCalledWith('/settings?tab=channels')
  })
})
