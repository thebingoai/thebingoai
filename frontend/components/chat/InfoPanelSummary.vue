<template>
  <div class="border-b border-gray-100">
    <!-- Header -->
    <button
      @click="chatStore.toggleInfoSection('summary')"
      class="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
    >
      <span class="text-[10px] uppercase tracking-wider text-gray-400 font-semibold">Summary</span>
      <div class="flex items-center gap-2">
        <span v-if="chatStore.conversationSummary?.updated_at" class="text-[10px] text-gray-300">
          {{ timeAgo }}
        </span>
        <svg
          class="w-3 h-3 text-gray-300 transition-transform duration-200"
          :class="{ 'rotate-180': chatStore.infoPanelSections.summary }"
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </div>
    </button>

    <!-- Content -->
    <div
      v-show="chatStore.infoPanelSections.summary"
      class="px-4 pb-3"
    >
      <!-- Summary text -->
      <p v-if="chatStore.conversationSummary?.text" class="text-xs text-gray-500 leading-relaxed mb-3">
        {{ chatStore.conversationSummary.text }}
      </p>
      <p v-else class="text-xs text-gray-300 italic mb-3">
        Start a conversation to see a summary here.
      </p>

      <!-- Token bar -->
      <div class="flex items-center gap-2">
        <div class="flex-1 h-1 bg-gray-100 rounded-full overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-500"
            :class="tokenBarColor"
            :style="{ width: tokenPercent + '%' }"
          />
        </div>
        <span class="text-[10px] text-gray-300 whitespace-nowrap">
          {{ formattedTokenCount }} / {{ formattedTokenLimit }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const chatStore = useChatStore()

const tokenCount = computed(() => chatStore.conversationSummary?.token_count ?? 0)
const tokenLimit = computed(() => chatStore.conversationSummary?.token_limit ?? 128000)

const tokenPercent = computed(() =>
  Math.min(100, (tokenCount.value / tokenLimit.value) * 100)
)

const tokenBarColor = computed(() => {
  const pct = tokenPercent.value
  if (pct >= 95) return 'bg-red-500'
  if (pct >= 80) return 'bg-amber-500'
  return 'bg-indigo-500'
})

const formatTokens = (n: number) => {
  if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k'
  return String(n)
}

const formattedTokenCount = computed(() => formatTokens(tokenCount.value))
const formattedTokenLimit = computed(() => formatTokens(tokenLimit.value))

// Time ago
const now = ref(Date.now())
let interval: ReturnType<typeof setInterval>
onMounted(() => { interval = setInterval(() => { now.value = Date.now() }, 60000) })
onUnmounted(() => clearInterval(interval))

const timeAgo = computed(() => {
  const updatedAt = chatStore.conversationSummary?.updated_at
  if (!updatedAt) return ''
  const diff = now.value - new Date(updatedAt).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
})
</script>
