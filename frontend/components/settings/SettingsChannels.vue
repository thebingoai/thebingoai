<template>
  <div class="p-6">
    <h2 class="text-2xl font-medium text-gray-900 dark:text-neutral-100 mb-1">Channels</h2>
    <p class="text-sm text-gray-500 dark:text-neutral-400 mb-6">Connect messaging platforms to your AI assistant.</p>

    <!-- Telegram Card — same compact shape for both states -->
    <UiCard class="relative overflow-hidden px-4 py-5 h-56 w-56 max-md:w-full">
      <!-- Status strip: green when connected, gray when not -->
      <div class="absolute top-0 left-0 right-0 h-[3px]" :class="status?.connected ? 'bg-green-500' : 'bg-gray-200 dark:bg-neutral-600'" />

      <div class="flex flex-col h-full">

        <!-- Header: icon + name + version badge -->
        <div class="flex items-start gap-2.5">
          <div class="h-8 w-8 shrink-0 rounded-full bg-sky-100 dark:bg-sky-900/30 flex items-center justify-center text-sky-500 dark:text-sky-400">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.833.941z"/>
            </svg>
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-1.5">
              <p class="text-sm font-semibold text-gray-900 dark:text-neutral-100 truncate">Telegram Bot</p>
              <span
                v-if="pluginInfo?.version"
                class="shrink-0 inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 dark:bg-neutral-700 text-gray-500 dark:text-neutral-400"
              >
                v{{ pluginInfo.version }}
              </span>
              <button
                v-if="pluginInfo?.changelog?.length"
                @click.stop="showChangelog = true"
                class="h-3.5 w-3.5 rounded-full border border-gray-300 dark:border-neutral-600 inline-flex items-center justify-center text-gray-400 dark:text-neutral-500 hover:text-gray-600 dark:hover:text-neutral-300 hover:border-gray-400 dark:hover:border-neutral-400"
              >
                <Info class="h-2 w-2" />
              </button>
            </div>
            <!-- Connected badge -->
            <span v-if="status?.connected" class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 mt-0.5">
              <span class="w-1.5 h-1.5 rounded-full bg-green-500 dark:bg-green-400 inline-block" />
              Connected
            </span>
            <span v-else class="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 dark:bg-neutral-700 text-gray-500 dark:text-neutral-400 mt-0.5">
              Not connected
            </span>
          </div>
        </div>

        <!-- Connected: bot username -->
        <template v-if="status?.connected">
          <p class="text-xs text-gray-500 dark:text-neutral-400 mt-2.5 font-medium truncate">@{{ status.bot_username }}</p>
        </template>

        <!-- Not connected: short description -->
        <template v-else>
          <p class="text-[11px] text-gray-500 dark:text-neutral-400 mt-2.5 leading-relaxed line-clamp-3">
            Connect a Telegram bot to chat with your AI assistant from Telegram.
          </p>
        </template>

        <!-- Action button -->
        <div class="mt-auto border-t border-gray-100 dark:border-neutral-700 pt-2.5">
          <template v-if="loading">
            <UiSkeleton class="h-7 w-full rounded" />
          </template>
          <template v-else-if="status?.connected">
            <UiButton variant="danger" size="sm" class="w-full" @click="showDisconnectDialog = true">
              Disconnect
            </UiButton>
          </template>
          <template v-else>
            <UiButton variant="primary" size="sm" class="w-full" @click="showConnectDialog = true">
              Connect
            </UiButton>
          </template>
        </div>
      </div>
    </UiCard>

    <!-- Connect dialog -->
    <UiDialog
      v-model:open="showConnectDialog"
      title="Connect Telegram Bot"
      size="sm"
    >
      <div class="p-6 flex flex-col gap-3">
        <p class="text-sm text-gray-500">
          Create a bot via <span class="font-medium text-gray-700">@BotFather</span> on Telegram, then paste the token below.
        </p>
        <UiInput
          v-model="botToken"
          placeholder="Bot token"
          :disabled="connecting"
        />
        <div>
          <UiInput
            v-model="telegramChatId"
            placeholder="Your Telegram chat ID"
            :disabled="connecting"
          />
          <p class="text-xs text-gray-400 mt-1">
            Send <span class="font-mono">/start</span> to @userinfobot to find your ID
          </p>
        </div>
        <div class="flex justify-end gap-2 pt-1">
          <UiButton variant="secondary" size="sm" @click="showConnectDialog = false">Cancel</UiButton>
          <UiButton
            variant="primary"
            size="sm"
            :loading="connecting"
            :disabled="!botToken.trim() || !telegramChatId.trim()"
            @click="handleConnect"
          >
            Connect
          </UiButton>
        </div>
      </div>
    </UiDialog>

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

    <!-- Changelog Bottom Sheet -->
    <UiBottomSheet
      :open="showChangelog"
      @update:open="showChangelog = $event"
      title="Telegram Bot Changelog"
    >
      <div class="divide-y divide-gray-100 dark:divide-neutral-700">
        <div
          v-for="entry in pluginInfo?.changelog"
          :key="entry.version"
          class="py-4 first:pt-0"
        >
          <div class="flex items-center gap-2 mb-2">
            <span class="text-sm font-semibold text-gray-900 dark:text-neutral-100">v{{ entry.version }}</span>
            <span class="text-xs text-gray-400 dark:text-neutral-500">{{ entry.date }}</span>
          </div>
          <ul class="space-y-1">
            <li
              v-for="(change, i) in entry.changes"
              :key="i"
              class="flex items-start gap-2 text-sm text-gray-600 dark:text-neutral-300"
            >
              <span class="mt-1.5 w-1 h-1 rounded-full bg-gray-400 dark:bg-neutral-500 shrink-0" />
              <span>{{ change }}</span>
            </li>
          </ul>
        </div>
      </div>
    </UiBottomSheet>
  </div>
</template>

<script setup lang="ts">
import { Info } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import type { TelegramBotStatus, TelegramBotInfo } from '~/utils/api/telegramApi'

const { telegram } = useApi()

const loading = ref(true)
const connecting = ref(false)
const disconnecting = ref(false)
const botToken = ref('')
const telegramChatId = ref('')
const status = ref<TelegramBotStatus | null>(null)
const pluginInfo = ref<TelegramBotInfo | null>(null)
const showConnectDialog = ref(false)
const showDisconnectDialog = ref(false)
const showChangelog = ref(false)

onMounted(async () => {
  try {
    const [s, info] = await Promise.all([
      telegram.getStatus(),
      telegram.getInfo().catch(() => null),
    ])
    status.value = s
    pluginInfo.value = info
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
    await telegram.setupBot(token, telegramChatId.value.trim())
    const [s, info] = await Promise.all([
      telegram.getStatus(),
      telegram.getInfo().catch(() => null),
    ])
    status.value = s
    pluginInfo.value = info
    botToken.value = ''
    telegramChatId.value = ''
    showConnectDialog.value = false
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
