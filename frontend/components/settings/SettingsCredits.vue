<template>
  <div class="p-6 space-y-8">
    <h2 class="text-2xl font-medium text-gray-900">Credits & API Keys</h2>

    <!-- Credit Meter -->
    <div class="rounded-xl border border-gray-200 p-6 space-y-3">
      <h3 class="text-base font-medium text-gray-900">Daily Credits</h3>
      <div class="flex items-center justify-between text-sm text-gray-600">
        <span>{{ Math.round(usedToday) }} used</span>
        <span>{{ dailyLimit }} daily limit</span>
      </div>
      <!-- Progress bar -->
      <div class="h-2 rounded-full bg-gray-100 overflow-hidden">
        <div
          class="h-full rounded-full transition-all duration-300"
          :class="usedPercent >= 90 ? 'bg-red-500' : usedPercent >= 70 ? 'bg-amber-500' : 'bg-emerald-500'"
          :style="{ width: `${usedPercent}%` }"
        />
      </div>
      <p class="text-xs text-gray-400">{{ Math.round(remaining) }} credits remaining today. Resets at midnight.</p>
    </div>

    <!-- Usage History -->
    <div class="rounded-xl border border-gray-200 p-6 space-y-4">
      <h3 class="text-base font-medium text-gray-900">Usage History</h3>

      <div v-if="historyLoading" class="space-y-2">
        <div v-for="i in 3" :key="i" class="h-10 rounded-lg bg-gray-100 animate-pulse" />
      </div>

      <div v-else-if="historyItems.length === 0" class="text-sm text-gray-400 py-4 text-center">
        No usage recorded yet.
      </div>

      <table v-else class="w-full text-sm">
        <thead>
          <tr class="text-left text-xs text-gray-400 border-b border-gray-100">
            <th class="pb-2 font-normal">Title</th>
            <th class="pb-2 font-normal text-right">Credits</th>
            <th class="pb-2 font-normal text-right">Date</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-50">
          <tr v-for="item in historyItems" :key="item.id" class="py-2">
            <td class="py-2 text-gray-700 truncate max-w-xs">{{ item.title }}</td>
            <td class="py-2 text-right tabular-nums text-gray-600">{{ item.credits_used.toFixed(4) }}</td>
            <td class="py-2 text-right text-gray-400 whitespace-nowrap">{{ formatDate(item.created_at) }}</td>
          </tr>
        </tbody>
      </table>

      <!-- Pagination -->
      <div v-if="historyTotalPages > 1" class="flex items-center justify-between text-sm">
        <button
          :disabled="historyPage <= 1"
          @click="prevPage"
          class="px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 disabled:opacity-40 hover:bg-gray-50 transition-colors"
        >
          Previous
        </button>
        <span class="text-xs text-gray-400">{{ historyPage }} / {{ historyTotalPages }}</span>
        <button
          :disabled="historyPage >= historyTotalPages"
          @click="nextPage"
          class="px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 disabled:opacity-40 hover:bg-gray-50 transition-colors"
        >
          Next
        </button>
      </div>
    </div>

    <!-- API Key Management -->
    <div class="rounded-xl border border-gray-200 p-6 space-y-4">
      <h3 class="text-base font-medium text-gray-900">Bring Your Own API Key</h3>
      <p class="text-sm text-gray-500">Use your own API keys to bypass daily credit limits.</p>

      <!-- Add key form -->
      <form @submit.prevent="handleSaveKey" class="space-y-3">
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Provider</label>
            <select
              v-model="newProvider"
              class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-gray-400"
            >
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">API Key</label>
            <input
              v-model="newApiKey"
              type="password"
              placeholder="sk-..."
              class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-gray-400"
              required
            />
          </div>
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-600 mb-1">
            Base URL <span class="text-gray-400">(optional)</span>
          </label>
          <input
            v-model="newBaseUrl"
            type="url"
            :placeholder="defaultBaseUrls[newProvider]"
            class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-gray-400"
          />
        </div>
        <button
          type="submit"
          :disabled="!newApiKey || saving"
          class="px-4 py-2 rounded-lg bg-gray-900 text-white text-sm disabled:opacity-40 hover:bg-gray-700 transition-colors"
        >
          {{ saving ? 'Saving...' : 'Save Key' }}
        </button>
      </form>

      <!-- Stored keys -->
      <div v-if="apiKeys.length > 0" class="space-y-2 pt-2">
        <div
          v-for="key in apiKeys"
          :key="key.provider"
          class="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50 px-4 py-3"
        >
          <div>
            <p class="text-sm font-medium text-gray-700 capitalize">{{ key.provider }}</p>
            <p class="text-xs text-gray-400 font-mono">{{ key.masked_key }}</p>
            <p v-if="key.api_base_url" class="text-xs text-gray-400">{{ key.api_base_url }}</p>
          </div>
          <button
            @click="handleDeleteKey(key.provider)"
            class="text-xs text-red-500 hover:text-red-700 transition-colors"
          >
            Remove
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const {
  dailyLimit, usedToday, remaining, usedPercent,
  historyItems, historyTotal, historyPage, historyTotalPages, historyLoading, nextPage, prevPage,
  apiKeys, saveApiKey, deleteApiKey,
} = useCreditSettings()

const defaultBaseUrls: Record<string, string> = {
  openai: 'https://api.openai.com/v1',
  anthropic: 'https://api.anthropic.com',
}

const newProvider = ref<'openai' | 'anthropic'>('openai')
const newApiKey = ref('')
const newBaseUrl = ref('')
const saving = ref(false)

// Pre-fill base URL when provider changes
watch(newProvider, (p) => {
  if (!newBaseUrl.value || Object.values(defaultBaseUrls).includes(newBaseUrl.value)) {
    newBaseUrl.value = defaultBaseUrls[p]
  }
})

async function handleSaveKey() {
  if (!newApiKey.value) return
  saving.value = true
  try {
    await saveApiKey(newProvider.value, newApiKey.value, newBaseUrl.value || undefined)
    newApiKey.value = ''
  } finally {
    saving.value = false
  }
}

async function handleDeleteKey(provider: string) {
  await deleteApiKey(provider)
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>
