import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, computed, reactive } from 'vue'

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('reactive', reactive)

// Stub Nuxt auto-imported composables used by the bubble
vi.stubGlobal('useChatStore', () => ({ isStreaming: false, messages: [], skillSuggestions: [] }))
vi.stubGlobal('useAuthStore', () => ({ user: { email: 'test@example.com' } }))
vi.stubGlobal('useApi', () => ({ skills: { respondToSuggestion: vi.fn() } }))
vi.stubGlobal('useMentions', () => ({ resolvedMentions: { value: new Map() } }))
vi.stubGlobal('navigateTo', vi.fn())

// Stub Pinia chat store used by the bubble (matches plan + protects against explicit import paths)
vi.mock('~/stores/chat', () => ({
  useChatStore: () => ({ isStreaming: false, messages: [], skillSuggestions: [] }),
}))

vi.mock('~/stores/dashboard', () => ({
  useDashboardStore: () => ({}),
}))

// Stub markdown renderer + briefing/skill children to avoid pulling their deps
vi.mock('~/components/ui/UiMarkdownRenderer.vue', () => ({
  default: { name: 'UiMarkdownRenderer', props: ['content'], template: '<div />' },
}))
vi.mock('~/components/chat/ChatSkillSuggestionCard.vue', () => ({
  default: { name: 'ChatSkillSuggestionCard', template: '<div />' },
}))
vi.mock('~/components/briefing/BriefingCard.vue', () => ({
  default: { name: 'BriefingCard', template: '<div />' },
}))

import ChatMessageBubble from '~/components/chat/ChatMessageBubble.vue'

const assistantMsg = {
  id: 'm1',
  role: 'assistant',
  content: 'Hello',
  source: 'chat',
  briefing_id: null,
}

describe('ChatMessageBubble', () => {
  function withChatStore(state: { isStreaming: boolean; messages?: any[] }) {
    vi.stubGlobal('useChatStore', () => ({
      isStreaming: state.isStreaming,
      messages: state.messages ?? [],
    }))
  }

  beforeEach(() => {
    withChatStore({ isStreaming: false })
  })

  it('renders both theme-aware logos for assistant avatar', () => {
    const wrapper = mount(ChatMessageBubble, {
      props: {
        message: assistantMsg,
        showActions: false,
        actionType: null,
        isLast: false,
        agentName: 'Bingo',
      },
    })
    const imgs = wrapper.findAll('img')
    const norm = (s: string | undefined) => (s ?? '').replace(/%20/g, ' ')
    const light = imgs.find(i => norm(i.attributes('src')) === '/logo/BINGO Logo Design_FA_Icon.png')
    const dark = imgs.find(i => norm(i.attributes('src')) === '/logo/BINGO Logo Design_FA_Icon_W.png')
    expect(light).toBeTruthy()
    expect(dark).toBeTruthy()
    expect(light!.classes()).toContain('dark:hidden')
    expect(dark!.classes()).toContain('hidden')
    expect(dark!.classes()).toContain('dark:block')
  })

  it('does not declare an agentAvatarUrl prop', () => {
    const wrapper = mount(ChatMessageBubble, {
      props: {
        message: assistantMsg,
        showActions: false,
        actionType: null,
        isLast: false,
        agentName: 'Bingo',
      },
    })
    const propsDef = (wrapper.vm as any).$options.props ?? {}
    // Positive control — if propsDef ever collapses to {} due to a compiler change,
    // this assertion will fail, preventing the absence check below from giving
    // a false-positive pass.
    expect('message' in propsDef).toBe(true)
    expect('agentAvatarUrl' in propsDef).toBe(false)
  })

  it('applies avatar-spin to the avatar wrapper when streaming and message empty (last bubble)', () => {
    withChatStore({ isStreaming: true })
    const wrapper = mount(ChatMessageBubble, {
      props: {
        message: { ...assistantMsg, content: '' },
        showActions: false,
        actionType: null,
        isLast: true,
        agentName: 'Bingo',
      },
    })
    const lightImg = wrapper.findAll('img').find(
      i => (i.attributes('src') ?? '').replace(/%20/g, ' ') === '/logo/BINGO Logo Design_FA_Icon.png'
    )!
    const avatarWrapper = lightImg.element.parentElement!
    expect(avatarWrapper.className).toContain('avatar-spin')
    expect(wrapper.find('.typing-indicator').exists()).toBe(false)
    expect(wrapper.findAll('.typing-dot').length).toBe(0)
  })

  it('does not apply avatar-spin when the message has content', () => {
    withChatStore({ isStreaming: true })
    const wrapper = mount(ChatMessageBubble, {
      props: {
        message: { ...assistantMsg, content: 'Hello' },
        showActions: false,
        actionType: null,
        isLast: true,
        agentName: 'Bingo',
      },
    })
    const lightImg = wrapper.findAll('img').find(
      i => (i.attributes('src') ?? '').replace(/%20/g, ' ') === '/logo/BINGO Logo Design_FA_Icon.png'
    )!
    const avatarWrapper = lightImg.element.parentElement!
    expect(avatarWrapper.className).not.toContain('avatar-spin')
  })
})
