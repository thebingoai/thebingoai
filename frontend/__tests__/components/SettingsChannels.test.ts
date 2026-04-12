import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, computed } from 'vue'

// ── Hoist mock variables so vi.mock factory can reference them ──────────
const { mockToast } = vi.hoisted(() => ({
  mockToast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('vue-sonner', () => ({
  toast: mockToast,
}))

// ── Nuxt auto-import stubs ──────────────────────────────────────────────
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('onMounted', vi.fn((cb: () => void) => cb()))

const mockGetStatus = vi.fn()
const mockSetupBot = vi.fn()
const mockDisconnect = vi.fn()

vi.stubGlobal('useApi', () => ({
  telegram: {
    getStatus: mockGetStatus,
    setupBot: mockSetupBot,
    disconnect: mockDisconnect,
    getInfo: vi.fn().mockResolvedValue(null),
  },
}))

import SettingsChannels from '~/components/settings/SettingsChannels.vue'

const stubs = {
  UiCard: { template: '<div class="ui-card"><slot /></div>' },
  UiButton: {
    template: '<button :disabled="disabled || loading" @click="$emit(\'click\')"><slot /></button>',
    props: ['variant', 'size', 'loading', 'disabled'],
    emits: ['click'],
  },
  UiInput: {
    template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
    props: ['modelValue', 'placeholder', 'disabled'],
    emits: ['update:modelValue'],
  },
  UiDialog: {
    template: '<div v-if="open" class="ui-dialog"><slot /></div>',
    props: ['open', 'title', 'size'],
    emits: ['update:open'],
  },
  UiSkeleton: { template: '<div class="skeleton" />' },
}

describe('SettingsChannels', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('not connected state', () => {
    it('shows token input and Connect button', async () => {
      mockGetStatus.mockResolvedValue({ connected: false, bot_username: null, is_active: false })
      const wrapper = mount(SettingsChannels, { global: { stubs } })
      await flushPromises()

      // The input lives inside the connect dialog — open it first
      const connectBtn = wrapper.findAll('button').find(b => b.text().toLowerCase().includes('connect'))
      await connectBtn!.trigger('click')
      await flushPromises()

      expect(wrapper.find('input').exists()).toBe(true)
      expect(wrapper.text()).toContain('BotFather')
      expect(wrapper.text()).not.toContain('Connected')
    })

    it('does not show disconnect button when not connected', async () => {
      mockGetStatus.mockResolvedValue({ connected: false, bot_username: null, is_active: false })
      const wrapper = mount(SettingsChannels, { global: { stubs } })
      await flushPromises()

      const buttons = wrapper.findAll('button')
      const disconnectBtn = buttons.find(b => b.text().toLowerCase().includes('disconnect'))
      expect(disconnectBtn).toBeUndefined()
    })
  })

  describe('connected state', () => {
    it('shows bot username and Disconnect button', async () => {
      mockGetStatus.mockResolvedValue({ connected: true, bot_username: 'test_bot', is_active: true })
      const wrapper = mount(SettingsChannels, { global: { stubs } })
      await flushPromises()

      expect(wrapper.text()).toContain('@test_bot')
      expect(wrapper.text()).toContain('Connected')
      const buttons = wrapper.findAll('button')
      const disconnectBtn = buttons.find(b => b.text().toLowerCase().includes('disconnect'))
      expect(disconnectBtn).toBeDefined()
    })

    it('does not show token input when connected', async () => {
      mockGetStatus.mockResolvedValue({ connected: true, bot_username: 'test_bot', is_active: true })
      const wrapper = mount(SettingsChannels, { global: { stubs } })
      await flushPromises()

      expect(wrapper.find('input').exists()).toBe(false)
    })
  })

  describe('connect flow', () => {
    it('calls setupBot with entered token and refreshes status', async () => {
      mockGetStatus
        .mockResolvedValueOnce({ connected: false, bot_username: null, is_active: false })
        .mockResolvedValueOnce({ connected: true, bot_username: 'new_bot', is_active: true })
      mockSetupBot.mockResolvedValue({ status: 'connected', bot_username: 'new_bot', webhook_url: 'https://example.com' })

      const wrapper = mount(SettingsChannels, { global: { stubs } })
      await flushPromises()

      // Open the connect dialog via the card's Connect button
      await wrapper.find('.ui-card button').trigger('click')
      await flushPromises()

      // Fill inputs inside the dialog
      const dialog = wrapper.find('.ui-dialog')
      const inputs = dialog.findAll('input')
      await inputs[0].setValue('123456:TEST-TOKEN')
      await inputs[1].setValue('99887766')

      // Click Connect inside the dialog
      const connectBtn = dialog.findAll('button').find(b => b.text() === 'Connect')
      await connectBtn!.trigger('click')
      await flushPromises()

      expect(mockSetupBot).toHaveBeenCalledWith('123456:TEST-TOKEN', '99887766')
      expect(wrapper.text()).toContain('@new_bot')
    })

    it('shows error toast when setupBot fails', async () => {
      mockGetStatus.mockResolvedValue({ connected: false, bot_username: null, is_active: false })
      mockSetupBot.mockRejectedValue({ data: { detail: 'Invalid token' } })

      const wrapper = mount(SettingsChannels, { global: { stubs } })
      await flushPromises()

      // Open the connect dialog via the card's Connect button
      await wrapper.find('.ui-card button').trigger('click')
      await flushPromises()

      // Fill inputs inside the dialog
      const dialog = wrapper.find('.ui-dialog')
      const inputs = dialog.findAll('input')
      await inputs[0].setValue('bad-token')
      await inputs[1].setValue('99887766')

      // Click Connect inside the dialog
      const connectBtn = dialog.findAll('button').find(b => b.text() === 'Connect')
      await connectBtn!.trigger('click')
      await flushPromises()

      expect(mockToast.error).toHaveBeenCalledWith('Invalid token')
    })
  })

  describe('disconnect flow', () => {
    it('calls disconnect and transitions to not-connected state', async () => {
      mockGetStatus.mockResolvedValue({ connected: true, bot_username: 'test_bot', is_active: true })
      mockDisconnect.mockResolvedValue(undefined)

      const wrapper = mount(SettingsChannels, { global: { stubs } })
      await flushPromises()

      // Open confirm dialog
      const disconnectBtn = wrapper.findAll('button').find(b => b.text().toLowerCase().includes('disconnect'))
      await disconnectBtn!.trigger('click')
      await flushPromises()

      // Confirm in dialog — find the Disconnect button inside the dialog
      const dialogDisconnectBtn = wrapper.findAll('button').filter(b => b.text().toLowerCase().includes('disconnect'))
      // last one is the confirm button inside dialog
      await dialogDisconnectBtn[dialogDisconnectBtn.length - 1].trigger('click')
      await flushPromises()

      expect(mockDisconnect).toHaveBeenCalled()
      expect(wrapper.text()).not.toContain('@test_bot')
      expect(mockToast.success).toHaveBeenCalledWith('Telegram bot disconnected')
    })

    it('shows error toast when disconnect fails', async () => {
      mockGetStatus.mockResolvedValue({ connected: true, bot_username: 'test_bot', is_active: true })
      mockDisconnect.mockRejectedValue(new Error('Network error'))

      const wrapper = mount(SettingsChannels, { global: { stubs } })
      await flushPromises()

      const disconnectBtn = wrapper.findAll('button').find(b => b.text().toLowerCase().includes('disconnect'))
      await disconnectBtn!.trigger('click')
      await flushPromises()

      const dialogDisconnectBtn = wrapper.findAll('button').filter(b => b.text().toLowerCase().includes('disconnect'))
      await dialogDisconnectBtn[dialogDisconnectBtn.length - 1].trigger('click')
      await flushPromises()

      expect(mockToast.error).toHaveBeenCalledWith('Failed to disconnect bot. Please try again.')
    })
  })
})
