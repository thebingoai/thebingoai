<template>
  <div
    class="group flex gap-4"
    :class="{
      'justify-end': message.role === 'user'
    }"
  >
    <!-- Avatar -->
    <div
      v-if="message.role === 'assistant'"
      class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-brand-100 dark:bg-brand-900/20"
    >
      <component :is="Bot" class="h-5 w-5 text-brand-600 dark:text-brand-400" />
    </div>

    <!-- Message Content -->
    <div class="max-w-[80%] min-w-0">
      <div
        class="rounded-lg px-4 py-3"
        :class="{
          'bg-brand-600 text-white dark:bg-brand-500': message.role === 'user',
          'bg-neutral-100 text-neutral-900 dark:bg-neutral-800 dark:text-neutral-100': message.role === 'assistant'
        }"
      >
        <!-- User Message -->
        <p v-if="message.role === 'user'" class="whitespace-pre-wrap break-words">
          {{ message.content }}
        </p>

        <!-- Assistant Message -->
        <div v-else>
          <div v-if="!message.content" class="text-neutral-500 dark:text-neutral-400 italic">
            Thinking...
          </div>
          <UiMarkdownRenderer v-else :content="message.content" />
        </div>
      </div>

      <!-- Sources -->
      <div v-if="message.role === 'assistant' && message.sources && message.sources.length > 0" class="mt-2">
        <details class="group/sources">
          <summary class="cursor-pointer text-xs text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-100">
            <component :is="FileText" class="mr-1 inline h-3 w-3" />
            {{ message.sources.length }} source{{ message.sources.length > 1 ? 's' : '' }}
          </summary>
          <div class="mt-2 space-y-1">
            <div
              v-for="(source, idx) in message.sources"
              :key="idx"
              class="rounded border border-neutral-200 bg-neutral-50 px-2 py-1 text-xs dark:border-neutral-700 dark:bg-neutral-900"
            >
              <span class="font-medium text-neutral-900 dark:text-neutral-100">
                {{ source.source }}
              </span>
              <span class="text-neutral-600 dark:text-neutral-400">
                (chunk {{ source.chunk_index }}, score: {{ (source.score * 100).toFixed(0) }}%)
              </span>
            </div>
          </div>
        </details>
      </div>

      <!-- Timestamp -->
      <p class="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
        {{ formatDate(message.timestamp, 'HH:mm') }}
      </p>
    </div>

    <!-- User Avatar -->
    <div
      v-if="message.role === 'user'"
      class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-neutral-200 dark:bg-neutral-700"
    >
      <component :is="User" class="h-5 w-5 text-neutral-600 dark:text-neutral-400" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Bot, User, FileText } from 'lucide-vue-next'
import type { ConversationMessage } from '~/types'
import { formatDate } from '~/utils/format'

interface Props {
  message: ConversationMessage
}

defineProps<Props>()
</script>
