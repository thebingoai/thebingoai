<template>
  <div class="h-full overflow-y-auto rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
    <div class="mb-4 flex items-center justify-between">
      <h2 class="font-normal text-neutral-900 dark:text-neutral-100">
        Conversations
      </h2>
      <UiButton size="sm" @click="$emit('new-chat')">
        New
      </UiButton>
    </div>

    <div v-if="conversations.length === 0" class="py-8 text-center">
      <p class="text-sm text-neutral-500 dark:text-neutral-400">
        No conversations yet
      </p>
    </div>

    <div v-else class="space-y-1">
      <button
        v-for="conversation in conversations"
        :key="conversation.id"
        @click="$emit('select', conversation.id)"
        class="flex w-full items-start gap-3 rounded-lg p-3 text-left transition-colors"
        :class="{
          'bg-brand-100 dark:bg-brand-900/20': selectedId === conversation.id,
          'hover:bg-neutral-100 dark:hover:bg-neutral-800': selectedId !== conversation.id
        }"
      >
        <component :is="MessageSquare" class="mt-0.5 h-4 w-4 flex-shrink-0 text-neutral-400" />
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-light text-neutral-900 dark:text-neutral-100">
            {{ conversation.title }}
          </p>
          <p class="mt-0.5 text-xs text-neutral-500 dark:text-neutral-400">
            {{ conversation.message_count }} messages · {{ timeAgo(conversation.updated_at) }}
          </p>
        </div>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { MessageSquare } from 'lucide-vue-next'
import type { Conversation } from '~/types'
import { timeAgo } from '~/utils/format'

interface Props {
  conversations: Conversation[]
  selectedId?: string | null
}

defineProps<Props>()

defineEmits<{
  select: [id: string]
  'new-chat': []
}>()
</script>
