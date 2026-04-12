// utils/api/telegramApi.ts

export interface TelegramBotStatus {
  connected: boolean
  bot_username: string | null
  is_active: boolean
}

export interface TelegramBotSetupResponse {
  status: string
  bot_username: string
  webhook_url: string
}

export function createTelegramApi(fetchWithRefresh: Function) {
  return {
    async getStatus(): Promise<TelegramBotStatus> {
      return fetchWithRefresh('/api/telegram/bot/status', { method: 'GET' })
    },

    async setupBot(botToken: string, telegramChatId: string): Promise<TelegramBotSetupResponse> {
      return fetchWithRefresh('/api/telegram/bot/setup', {
        method: 'POST',
        body: {
          bot_token: botToken,
          telegram_chat_id: parseInt(telegramChatId, 10),
        },
      })
    },

    async disconnect(): Promise<void> {
      return fetchWithRefresh('/api/telegram/bot/disconnect', { method: 'DELETE' })
    },
  }
}
