<template>
  <div class="mb-6">
    <!-- User message: left-aligned chat bubble -->
    <div v-if="message.role === 'user'">
      <div class="inline-block bg-gray-900 text-white rounded-2xl px-4 py-2.5 max-w-[80%] whitespace-pre-wrap">
        {{ message.content }}
      </div>
    </div>

    <!-- Assistant message: left-aligned plain text -->
    <div v-else class="pr-32">
      <!-- Typing indicator when assistant message is empty during streaming -->
      <div v-if="!message.content && chatStore.isStreaming" class="typing-indicator">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
      </div>

      <!-- Assistant message with markdown -->
      <UiMarkdownRenderer v-else :content="message.content" />

      <!-- SQL Query -->
      <div v-if="message.sql" class="mt-3">
        <div class="rounded-lg bg-gray-50 p-4">
          <pre class="text-sm"><code>{{ message.sql }}</code></pre>
        </div>
      </div>

      <!-- Results Table -->
      <div v-if="message.results && message.results.length > 0" class="mt-3 overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200 border border-gray-200 rounded-lg">
          <thead class="bg-gray-50">
            <tr>
              <th
                v-for="(value, key) in message.results[0]"
                :key="key"
                class="px-4 py-2 text-left text-xs font-normal text-gray-700"
              >
                {{ key }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200 bg-white">
            <tr v-for="(row, idx) in message.results.slice(0, 50)" :key="idx">
              <td
                v-for="(value, key) in row"
                :key="key"
                class="px-4 py-2 text-sm text-gray-900"
              >
                {{ value }}
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="message.results.length > 50" class="mt-2 text-sm text-gray-500">
          Showing 50 of {{ message.results.length }} rows
        </p>
      </div>

      <!-- Agent steps / reasoning toggle -->
      <div v-if="hasSteps" class="mt-3">
        <button
          @click="openReasoning"
          class="inline-flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-600 transition-colors"
        >
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.347.15A4.98 4.98 0 0112 17a4.98 4.98 0 01-2.39-.606l-.347-.15z" />
          </svg>
          <span>{{ stepCount }} reasoning step{{ stepCount !== 1 ? 's' : '' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Message } from '~/stores/chat'

const props = defineProps<{
  message: Message
}>()

const chatStore = useChatStore()

const hasSteps = computed(() =>
  props.message.role === 'assistant' &&
  (props.message.agent_steps?.length || props.message.thinking_steps?.length)
)

const stepCount = computed(() =>
  props.message.agent_steps?.length || props.message.thinking_steps?.length || 0
)

const openReasoning = () => {
  chatStore.openReasoningPanel(props.message.id)
}
</script>

<style scoped>
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 8px 0;
}

.typing-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #9ca3af;
  animation: typing-bounce 1.4s infinite ease-in-out;
}

.typing-dot:nth-child(1) {
  animation-delay: 0s;
}

.typing-dot:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing-bounce {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.7;
  }
  30% {
    transform: translateY(-10px);
    opacity: 1;
  }
}
</style>
