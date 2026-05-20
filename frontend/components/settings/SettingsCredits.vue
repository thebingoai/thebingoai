<template>
  <div class="flex flex-col h-full overflow-hidden">

    <!-- Page header -->
    <div class="px-7 pt-3 pb-2 border-b border-[var(--line)] flex-shrink-0">
      <p class="eyebrow mb-0.5 text-gray-400 dark:text-neutral-500">Settings · Credits</p>
      <h1 class="settings-h1 text-3xl text-gray-900 dark:text-white mb-1">Credits & API Keys</h1>
    </div>

    <!-- Scrolling body -->
    <div class="flex-1 overflow-y-auto px-7 py-6 space-y-6">

      <!-- Section 1: Daily Credits + Daily Consumption -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">

        <!-- Daily Credits -->
        <div class="rounded-xl border border-gray-200 dark:border-neutral-700 p-6 flex flex-col gap-3">
          <p class="text-[10px] font-medium tracking-wider uppercase text-gray-400 dark:text-neutral-500">Daily Credits</p>
          <div class="flex items-baseline gap-2">
            <span class="text-5xl font-semibold tabular-nums text-gray-900 dark:text-white">{{ Math.round(remaining) }}</span>
            <span class="text-sm text-gray-500 dark:text-neutral-400">of {{ Math.round(dailyLimit) }} remaining</span>
          </div>
          <div class="h-1 rounded-full bg-gray-100 dark:bg-neutral-700 overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-300"
              :class="usedPercent >= 90 ? 'bg-red-500' : 'bar-orange-flow'"
              :style="{ width: `${usedPercent}%` }"
            />
          </div>
          <p class="text-xs text-gray-400 dark:text-neutral-500">
            {{ Math.round(usedToday) }} used today · resets at 00:00 UTC<span v-if="resetCountdown"> · {{ resetCountdown }}</span>
          </p>
        </div>

        <!-- Daily Consumption -->
        <div class="rounded-xl border border-gray-200 dark:border-neutral-700 p-6 flex flex-col gap-3">
          <p class="text-[10px] font-medium tracking-wider uppercase text-gray-400 dark:text-neutral-500">Daily Consumption · Last 14 Days</p>
          <div class="flex-1 min-h-[160px] flex flex-col justify-center">
            <div v-if="dailyTotalsLoading" class="h-40 rounded-lg bg-gray-100 dark:bg-neutral-700 animate-pulse" />
            <div v-else-if="dailyTotals.length === 0" class="h-40 flex items-center justify-center text-sm text-gray-400 dark:text-neutral-500">
              No usage data yet.
            </div>
            <canvas v-else ref="chartCanvas" class="h-40" />
          </div>
        </div>

      </div>

      <!-- Section 2: Bring Your Own API Key -->
      <div class="rounded-xl border border-gray-200 dark:border-neutral-700 p-6 space-y-4">
        <div>
          <h3 class="text-base font-medium text-gray-900 dark:text-white">Bring your own API key</h3>
          <p class="text-sm text-gray-500 dark:text-neutral-400 mt-1">Use your own API keys to bypass daily credit limits. Usage rolls up on your provider's invoice, not ours.</p>
        </div>

        <!-- Stored keys -->
        <div v-if="apiKeys.length > 0" class="divide-y divide-gray-100 dark:divide-neutral-700/50">
          <div
            v-for="key in apiKeys"
            :key="key.provider"
            class="flex items-center justify-between py-3"
          >
            <div class="flex items-center gap-3 min-w-0 flex-1">
              <span class="inline-flex items-center justify-center w-7 h-7 rounded-md bg-neutral-900 dark:bg-neutral-700 text-white text-xs font-semibold shrink-0">
                {{ key.provider.charAt(0).toUpperCase() }}
              </span>
              <div class="min-w-0">
                <div class="flex items-center gap-2 mb-0.5">
                  <p class="text-sm font-medium text-gray-700 dark:text-neutral-200 capitalize">{{ key.provider }}</p>
                  <span
                    v-if="(key as any).is_active"
                    class="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
                  >in use</span>
                </div>
                <p class="text-xs font-mono text-gray-400 dark:text-neutral-500">{{ key.masked_key }}</p>
                <p v-if="key.api_base_url" class="text-xs text-gray-400 dark:text-neutral-500">{{ key.api_base_url }}</p>
                <p v-if="(key as any).last_used_at" class="text-xs text-gray-400 dark:text-neutral-500">
                  Last used {{ formatDate((key as any).last_used_at) }}
                </p>
              </div>
            </div>
            <button
              @click="handleDeleteKey(key.provider)"
              class="text-xs text-red-500 hover:text-red-700 transition-colors shrink-0 ml-4"
            >
              Remove
            </button>
          </div>
        </div>
        <p v-else class="text-sm text-gray-400 dark:text-neutral-500">No API keys configured.</p>

        <!-- Add new key -->
        <div class="pt-4 border-t border-gray-100 dark:border-neutral-700 space-y-3">
          <p class="text-[10px] font-medium tracking-wider uppercase text-gray-400 dark:text-neutral-500">Add a new key</p>
          <form @submit.prevent="handleSaveKey" class="grid grid-cols-1 sm:grid-cols-[180px_1fr_1fr_auto] gap-3 items-end">
            <div>
              <label class="block text-xs font-medium text-gray-600 dark:text-neutral-300 mb-1">Provider</label>
              <select
                v-model="newProvider"
                class="w-full rounded-lg border border-gray-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-gray-900 dark:text-neutral-100 px-3 py-2 text-sm focus:outline-none focus:border-gray-400 dark:[color-scheme:dark]"
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-600 dark:text-neutral-300 mb-1">
                Base URL <span class="text-gray-400 dark:text-neutral-500">(optional)</span>
              </label>
              <input
                v-model="newBaseUrl"
                type="url"
                :placeholder="defaultBaseUrls[newProvider]"
                class="w-full rounded-lg border border-gray-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-gray-900 dark:text-neutral-100 placeholder:text-gray-400 dark:placeholder:text-neutral-500 px-3 py-2 text-sm focus:outline-none focus:border-gray-400 dark:[color-scheme:dark]"
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-600 dark:text-neutral-300 mb-1">API Key</label>
              <input
                v-model="newApiKey"
                type="password"
                placeholder="sk-..."
                class="w-full rounded-lg border border-gray-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-gray-900 dark:text-neutral-100 placeholder:text-gray-400 dark:placeholder:text-neutral-500 px-3 py-2 text-sm focus:outline-none focus:border-gray-400 dark:[color-scheme:dark]"
                required
              />
            </div>
            <button
              type="submit"
              :disabled="!newApiKey || saving"
              class="px-4 py-2 rounded-lg bg-neutral-900 dark:bg-white text-white dark:text-gray-900 text-sm disabled:opacity-40 hover:bg-neutral-700 dark:hover:bg-gray-100 transition-colors whitespace-nowrap"
            >
              {{ saving ? 'Saving...' : 'Save key' }}
            </button>
          </form>
        </div>
      </div>

      <!-- Section 3: Usage History -->
      <div class="rounded-xl border border-gray-200 dark:border-neutral-700 p-6 space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="text-base font-medium text-gray-900 dark:text-white">Usage History</h3>
          <button
            @click="handleExportCsv"
            class="text-xs px-3 py-1.5 rounded-md border border-gray-200 dark:border-neutral-600 text-gray-600 dark:text-neutral-300 hover:bg-gray-50 dark:hover:bg-neutral-700 transition-colors"
          >
            Export CSV
          </button>
        </div>

        <div v-if="historyLoading" class="space-y-2">
          <div v-for="i in 3" :key="i" class="h-10 rounded-lg bg-gray-100 dark:bg-neutral-700 animate-pulse" />
        </div>

        <div v-else-if="historyItems.length === 0" class="text-sm text-gray-400 dark:text-neutral-500 py-4 text-center">
          No usage recorded yet.
        </div>

        <table v-else class="w-full text-sm">
          <thead>
            <tr class="text-left text-xs text-gray-400 dark:text-neutral-500 border-b border-gray-100 dark:border-neutral-700">
              <th class="pb-2 font-normal">Title</th>
              <th v-if="hasModelField" class="pb-2 font-normal">Model</th>
              <th v-if="hasTokensField" class="pb-2 font-normal text-right">Tokens</th>
              <th class="pb-2 font-normal text-right">Credits</th>
              <th class="pb-2 font-normal text-right">Date</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-50 dark:divide-neutral-700/50">
            <tr v-for="item in historyItems" :key="item.id" class="py-2">
              <td class="py-2 text-gray-700 dark:text-neutral-300 truncate max-w-xs">{{ item.title }}</td>
              <td v-if="hasModelField" class="py-2 text-xs text-gray-500 dark:text-neutral-400 font-mono">{{ (item as any).model }}</td>
              <td v-if="hasTokensField" class="py-2 text-right tabular-nums text-xs text-gray-500 dark:text-neutral-400">{{ (item as any).tokens }}</td>
              <td class="py-2 text-right tabular-nums text-gray-600 dark:text-neutral-300">{{ item.credits_used }}</td>
              <td class="py-2 text-right text-gray-400 dark:text-neutral-500 whitespace-nowrap">{{ formatDate(item.created_at) }}</td>
            </tr>
          </tbody>
        </table>

        <!-- Pagination -->
        <div v-if="historyTotalPages > 1" class="flex items-center justify-between text-sm">
          <button
            :disabled="historyPage <= 1"
            @click="prevPage"
            class="px-3 py-1.5 rounded-lg border border-gray-200 dark:border-neutral-600 text-gray-600 dark:text-neutral-300 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-neutral-700 transition-colors"
          >
            Previous
          </button>
          <span class="text-xs text-gray-400 dark:text-neutral-500">{{ historyPage }} / {{ historyTotalPages }}</span>
          <button
            :disabled="historyPage >= historyTotalPages"
            @click="nextPage"
            class="px-3 py-1.5 rounded-lg border border-gray-200 dark:border-neutral-600 text-gray-600 dark:text-neutral-300 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-neutral-700 transition-colors"
          >
            Next
          </button>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { differenceInMinutes } from 'date-fns'
import { parseUtcDate } from '~/utils/format'

const {
  dailyLimit, usedToday, remaining, usedPercent, resetsAt,
  historyItems, historyPage, historyTotalPages, historyLoading, nextPage, prevPage,
  dailyTotals, dailyTotalsLoading,
  apiKeys, saveApiKey, deleteApiKey,
  exportHistoryCsv,
} = useCreditSettings()

const resetCountdown = computed(() => {
  if (!resetsAt.value) return null
  const mins = differenceInMinutes(new Date(resetsAt.value), new Date())
  if (mins <= 0) return null
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return h > 0 ? `in ${h}h ${m}m` : `in ${m}m`
})

const hasModelField = computed(() => historyItems.value.some(i => (i as any).model != null))
const hasTokensField = computed(() => historyItems.value.some(i => (i as any).tokens != null))

// ----- Consumption chart -----
const chartCanvas = ref<HTMLCanvasElement | null>(null)

const chartConfig = computed<import('~/types/chart').ChartConfig>(() => {
  const labels = dailyTotals.value.map(d => {
    const dt = new Date(d.date + 'T00:00:00')
    return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  })
  const data = dailyTotals.value.map(d => Math.round(d.total * 100) / 100)

  return {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Credits Used',
        data,
        backgroundColor: '#f97316',
        borderColor: '#ea580c',
        borderWidth: 1,
      }],
    },
    options: {
      showLegend: false,
      showGrid: false,
      showTooltips: true,
      showValues: false,
    },
  }
})

useChart(chartCanvas, chartConfig)

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

async function handleExportCsv() {
  await exportHistoryCsv()
}

function formatDate(iso: string): string {
  return parseUtcDate(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.bar-orange-flow {
  background: linear-gradient(90deg, #f97316, #fb923c, #fdba74, #fb923c, #f97316);
  background-size: 200% 100%;
  animation: bar-glow-sweep 2s ease-in-out infinite;
}

@keyframes bar-glow-sweep {
  0% { background-position: 100% 0; }
  100% { background-position: -100% 0; }
}
</style>
