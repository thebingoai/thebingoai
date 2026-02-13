<template>
  <div class="flex h-screen">
    <div class="flex-1 flex flex-col p-6">
      <div class="flex justify-between items-center mb-4">
        <h1 class="text-2xl font-bold">Chat</h1>
        <button @click="chat.newConversation()"
          class="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">
          New Chat
        </button>
      </div>

      <div class="flex-1 overflow-y-auto mb-4 space-y-4">
        <div v-if="chat.messages.value.length === 0"
          class="text-center text-gray-500 py-8">
          Start a conversation...
        </div>

        <div v-for="(msg, idx) in chat.messages.value" :key="idx"
          :class="['p-4 rounded-lg', msg.role === 'user' ? 'bg-blue-100 ml-12' : 'bg-gray-100 mr-12']">
          <div class="font-semibold mb-2">{{ msg.role === 'user' ? 'You' : 'Assistant' }}</div>
          <div class="whitespace-pre-wrap">{{ msg.content }}</div>

          <div v-if="msg.sql_queries && msg.sql_queries.length > 0" class="mt-4">
            <div class="text-sm font-semibold mb-2">SQL:</div>
            <pre class="bg-gray-800 text-white p-3 rounded text-sm overflow-x-auto">{{ msg.sql_queries.join('\n') }}</pre>
          </div>

          <div v-if="msg.results && msg.results.length > 0" class="mt-4">
            <div class="text-sm font-semibold mb-2">Results ({{ msg.results.length }} rows):</div>
            <div class="overflow-x-auto">
              <table class="min-w-full border text-sm">
                <thead class="bg-gray-50">
                  <tr>
                    <th v-for="key in Object.keys(msg.results[0])" :key="key"
                      class="border px-3 py-2 text-left">{{ key }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, i) in msg.results.slice(0, 10)" :key="i">
                    <td v-for="key in Object.keys(row)" :key="key"
                      class="border px-3 py-2">{{ row[key] }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <form @submit.prevent="handleSend" class="flex gap-2">
        <input v-model="message" :disabled="chat.loading.value"
          placeholder="Ask a question..."
          class="flex-1 px-4 py-2 border rounded-md" />
        <button type="submit" :disabled="chat.loading.value || !message"
          class="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50">
          {{ chat.loading.value ? 'Sending...' : 'Send' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: 'auth'
})

const chat = useNewChat()
const message = ref('')

async function handleSend() {
  if (!message.value.trim()) return

  try {
    await chat.sendMessage({
      message: message.value,
      connection_ids: []
    })
    message.value = ''
  } catch (error: any) {
    console.error('Send failed:', error)
  }
}

onMounted(() => {
  chat.loadConversations()
})
</script>
