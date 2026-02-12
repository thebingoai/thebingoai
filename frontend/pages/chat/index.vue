<template>
  <div class="flex h-[calc(100vh-4rem)] flex-col lg:flex-row">
    <!-- Conversation Sidebar (Desktop) -->
    <div class="hidden h-full w-80 flex-shrink-0 border-r border-neutral-200 p-4 dark:border-neutral-800 lg:block">
      <ConversationList
        :conversations="chatStore.sortedConversations"
        :selected-id="chatStore.currentConversationId"
        @select="selectConversation"
        @new-chat="startNewChat"
      />
    </div>

    <!-- Main Chat Area -->
    <div class="flex flex-1 flex-col overflow-hidden">
      <!-- Empty State -->
      <div v-if="!chatStore.currentConversationId" class="flex flex-1 flex-col items-center justify-center p-6">
        <div class="max-w-2xl text-center">
          <div class="mb-6 rounded-full bg-brand-100 p-6 inline-block dark:bg-brand-900/20">
            <component :is="MessageSquare" class="h-12 w-12 text-brand-600 dark:text-brand-400" />
          </div>

          <h2 class="mb-4 text-3xl font-bold text-neutral-900 dark:text-neutral-100">
            Start a Conversation
          </h2>

          <p class="mb-8 text-neutral-600 dark:text-neutral-400">
            Ask questions about your documents and get AI-powered answers with citations.
          </p>

          <div class="grid gap-3 sm:grid-cols-2">
            <button
              v-for="suggestion in suggestions"
              :key="suggestion"
              @click="handleSuggestion(suggestion)"
              class="rounded-lg border border-neutral-200 p-4 text-left transition-all hover:border-brand-300 hover:shadow-md dark:border-neutral-800 dark:hover:border-brand-700"
            >
              <p class="text-sm text-neutral-900 dark:text-neutral-100">
                {{ suggestion }}
              </p>
            </button>
          </div>
        </div>
      </div>

      <!-- Messages -->
      <div
        v-else
        ref="messagesContainer"
        class="flex-1 overflow-y-auto p-6"
      >
        <div class="mx-auto max-w-4xl space-y-6">
          <ChatMessage
            v-for="message in chatStore.messages"
            :key="message.id"
            :message="message"
          />
        </div>
      </div>

      <!-- Input -->
      <ChatInput
        @send="handleSend"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { MessageSquare } from 'lucide-vue-next'

const chatStore = useChatStore()
const { sendMessage } = useChat()

const messagesContainer = ref<HTMLElement>()

const suggestions = [
  'How do I get started with this project?',
  'Explain the architecture',
  'What are the main features?',
  'Show me code examples'
]

const selectConversation = (id: string) => {
  chatStore.setCurrentConversation(id)
  // Load messages for this conversation (in a real app)
}

const startNewChat = () => {
  chatStore.setCurrentConversation(null)
}

const handleSend = async (message: string) => {
  await sendMessage(message)
  await nextTick()
  scrollToBottom()
}

const handleSuggestion = (suggestion: string) => {
  chatStore.setInputText(suggestion)
  handleSend(suggestion)
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}
</script>
