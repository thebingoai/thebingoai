import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createTelegramApi } from '~/utils/api/telegramApi'

describe('createTelegramApi', () => {
  let fetchWithRefresh: ReturnType<typeof vi.fn>
  let api: ReturnType<typeof createTelegramApi>

  beforeEach(() => {
    fetchWithRefresh = vi.fn()
    api = createTelegramApi(fetchWithRefresh)
  })

  describe('getStatus', () => {
    it('calls GET /api/telegram/bot/status', async () => {
      fetchWithRefresh.mockResolvedValue({ connected: true, bot_username: 'mybot', is_active: true })
      const result = await api.getStatus()
      expect(fetchWithRefresh).toHaveBeenCalledWith('/api/telegram/bot/status', { method: 'GET' })
      expect(result).toEqual({ connected: true, bot_username: 'mybot', is_active: true })
    })

    it('returns connected: false when not configured', async () => {
      fetchWithRefresh.mockResolvedValue({ connected: false, bot_username: null, is_active: false })
      const result = await api.getStatus()
      expect(result.connected).toBe(false)
    })
  })

  describe('setupBot', () => {
    it('calls POST /api/telegram/bot/setup with bot_token in body', async () => {
      fetchWithRefresh.mockResolvedValue({ status: 'connected', bot_username: 'mybot', webhook_url: 'https://example.com/webhook' })
      const result = await api.setupBot('123456:ABC-TOKEN')
      expect(fetchWithRefresh).toHaveBeenCalledWith('/api/telegram/bot/setup', {
        method: 'POST',
        body: { bot_token: '123456:ABC-TOKEN' },
      })
      expect(result.status).toBe('connected')
      expect(result.bot_username).toBe('mybot')
    })
  })

  describe('disconnect', () => {
    it('calls DELETE /api/telegram/bot/disconnect', async () => {
      fetchWithRefresh.mockResolvedValue(undefined)
      await api.disconnect()
      expect(fetchWithRefresh).toHaveBeenCalledWith('/api/telegram/bot/disconnect', { method: 'DELETE' })
    })
  })
})
