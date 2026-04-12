<template>
  <div class="p-6">
    <h2 class="text-2xl font-medium text-gray-900 mb-1">Channels</h2>
    <p class="text-sm text-gray-500 mb-6">Connect messaging platforms to your AI assistant.</p>

    <!-- Telegram Card -->
    <UiCard class="p-6">
      <div class="flex items-start gap-4">
        <!-- Telegram icon -->
        <div class="flex-shrink-0 w-10 h-10 rounded-full bg-sky-100 flex items-center justify-center text-sky-500">
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.833.941z"/>
          </svg>
        </div>

        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <h3 class="text-sm font-medium text-gray-900">Telegram Bot</h3>
            <span
              v-if="status?.connected"
              class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700"
            >
              Connected
            </span>
          </div>

          <!-- Connected state -->
          <template v-if="status?.connected">
            <p class="text-sm text-gray-500 mb-4">
              Bot <span class="font-medium text-gray-700">@{{ status.bot_username }}</span> is active and receiving messages.
            </p>
            <UiButton variant="danger" size="sm" @click="showDisconnectDialog = true">
              Disconnect
            </UiButton>
          </template>

          <!-- Not connected state -->
          <template v-else-if="!loading">
            <p class="text-sm text-gray-500 mb-3">
              Connect a Telegram bot to let users message your AI assistant directly.
              Create a bot via <span class="font-medium text-gray-700">@BotFather</span> on Telegram and paste the token below.
            </p>
            <div class="flex items-center gap-2">
              <UiInput
                v-model="botToken"
                placeholder="123456:ABC-DEF1234ghIkl..."
                class="flex-1"
                :disabled="connecting"
              />
              <UiButton
                variant="primary"
                size="sm"
                :loading="connecting"
                :disabled="!botToken.trim()"
                @click="handleConnect"
              >
                Connect
              </UiButton>
            </div>
          </template>

          <div v-else class="h-8 flex items-center">
            <UiSkeleton class="h-4 w-48" />
          </div>
        </div>
      </div>
    </UiCard>

    <!-- Disconnect confirmation dialog -->
    <UiDialog
      v-model:open="showDisconnectDialog"
      title="Disconnect Telegram Bot"
      size="sm"
    >
      <div class="p-6">
        <p class="text-sm text-gray-600 mb-6">
          This will unregister the webhook and remove your bot configuration. You can reconnect at any time.
        </p>
        <div class="flex justify-end gap-2">
          <UiButton variant="secondary" size="sm" @click="showDisconnectDialog = false">
            Cancel
          </UiButton>
          <UiButton variant="danger" size="sm" :loading="disconnecting" @click="handleDisconnect">
            Disconnect
          </UiButton>
        </div>
      </div>
    </UiDialog>
  </div>
</template>

<script setup lang="ts">
import { toast } from 'vue-sonner'
import type { TelegramBotStatus } from '~/utils/api/telegramApi'

const { telegram } = useApi()

const loading = ref(true)
const connecting = ref(false)
const disconnecting = ref(false)
const botToken = ref('')
const status = ref<TelegramBotStatus | null>(null)
const showDisconnectDialog = ref(false)

onMounted(async () => {
  try {
    status.value = await telegram.getStatus()
  } catch {
    // stay in not-connected state
  } finally {
    loading.value = false
  }
})

const handleConnect = async () => {
  const token = botToken.value.trim()
  if (!token) return
  connecting.value = true
  try {
    await telegram.setupBot(token)
    status.value = await telegram.getStatus()
    botToken.value = ''
    toast.success('Telegram bot connected')
  } catch (err: any) {
    toast.error(err?.data?.detail || 'Failed to connect bot. Check your token and try again.')
  } finally {
    connecting.value = false
  }
}

const handleDisconnect = async () => {
  disconnecting.value = true
  try {
    await telegram.disconnect()
    status.value = { connected: false, bot_username: null, is_active: false }
    showDisconnectDialog.value = false
    toast.success('Telegram bot disconnected')
  } catch {
    toast.error('Failed to disconnect bot. Please try again.')
  } finally {
    disconnecting.value = false
  }
}
</script>
