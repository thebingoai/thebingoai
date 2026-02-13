<template>
  <div class="mb-6">
    <div class="mb-2 flex items-center gap-2">
      <div
        class="flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium"
        :class="message.role === 'user' ? 'bg-gray-900 text-white' : 'bg-gray-200 text-gray-900'"
      >
        {{ message.role === 'user' ? 'U' : 'AI' }}
      </div>
      <span class="text-sm font-medium text-gray-900">
        {{ message.role === 'user' ? 'You' : 'Assistant' }}
      </span>
    </div>

    <div class="ml-10">
      <!-- Typing indicator when assistant message is empty during streaming -->
      <div v-if="message.role === 'assistant' && !message.content && chatStore.isStreaming" class="typing-indicator">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
      </div>

      <!-- Assistant message with markdown -->
      <UiMarkdownRenderer v-else-if="message.role === 'assistant'" :content="message.content" />

      <!-- User message as plain text -->
      <div v-else class="prose-chat whitespace-pre-wrap">{{ message.content }}</div>

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
                class="px-4 py-2 text-left text-xs font-semibold text-gray-700"
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

      <!-- Thinking Steps -->
      <div v-if="message.thinking_steps && message.thinking_steps.length > 0" class="mt-3">
        <button
          @click="chatStore.toggleThinking(message.id)"
          class="text-sm text-gray-500 hover:text-gray-700"
        >
          {{ chatStore.expandedThinking.has(message.id) ? '▼' : '▸' }} Show thinking ({{ message.thinking_steps.length }} steps)
        </button>
        <div v-if="chatStore.expandedThinking.has(message.id)" class="mt-2 space-y-2">
          <div
            v-for="(step, idx) in message.thinking_steps"
            :key="idx"
            class="rounded-lg bg-gray-50 p-3"
          >
            <div class="text-sm font-medium text-gray-900">{{ step.step }}</div>
            <div class="text-sm text-gray-600">{{ step.description }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Message } from '~/stores/chat'

defineProps<{
  message: Message
}>()

const chatStore = useChatStore()
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
