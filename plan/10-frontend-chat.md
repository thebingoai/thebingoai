# Phase 10: Frontend Chat Interface

## Objective

Build chat interface with natural language input, SQL display, data tables, Chart.js visualizations, connection selector, and SSE streaming.

## Prerequisites

- Phase 05: Chat API
- Phase 09: Frontend Auth & Connections

## Files to Create

### Pages
- `frontend/pages/index.vue` - Main chat interface
- `frontend/pages/chat/[threadId].vue` - Conversation view

### Components
- `frontend/components/ChatInput.vue` - Message input with connection selector
- `frontend/components/ChatMessage.vue` - Message bubble (user/assistant)
- `frontend/components/SQLDisplay.vue` - Syntax-highlighted SQL
- `frontend/components/DataTable.vue` - Query results table
- `frontend/components/DataChart.vue` - Chart.js visualization
- `frontend/components/ConversationList.vue` - Sidebar with conversations

### Composables
- `frontend/composables/useChat.ts` - Chat state and SSE streaming
- `frontend/composables/useConversations.ts` - Conversation management

### Types
- `frontend/types/chat.ts` - Chat message, response types

### Utils
- `frontend/utils/chartGenerator.ts` - Auto-generate charts from data
- `frontend/utils/sqlHighlight.ts` - SQL syntax highlighting

## Implementation Details

### 1. Chat Composable (frontend/composables/useChat.ts)

```typescript
import type { ChatMessage, ChatRequest, ChatResponse } from '~/types/chat'

export const useChat = () => {
  const api = useApi()
  const messages = ref<ChatMessage[]>([])
  const loading = ref(false)
  const currentThreadId = ref<string | null>(null)

  async function sendMessage(request: ChatRequest) {
    loading.value = true

    // Add user message immediately
    messages.value.push({
      role: 'user',
      content: request.message,
      timestamp: new Date().toISOString()
    })

    try {
      const response = await api.post<ChatResponse>('/api/chat', request)

      // Add assistant message
      messages.value.push({
        role: 'assistant',
        content: response.message,
        timestamp: new Date().toISOString(),
        sql: response.sql,
        result: response.result,
        error: response.error
      })

      currentThreadId.value = response.thread_id
      return response
    } catch (error) {
      messages.value.push({
        role: 'assistant',
        content: 'Error: Failed to process message',
        timestamp: new Date().toISOString(),
        error: 'Request failed'
      })
      throw error
    } finally {
      loading.value = false
    }
  }

  async function sendMessageStream(request: ChatRequest) {
    loading.value = true

    // Add user message
    messages.value.push({
      role: 'user',
      content: request.message,
      timestamp: new Date().toISOString()
    })

    // Create placeholder for assistant message
    const assistantMessage: ChatMessage = {
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString()
    }
    messages.value.push(assistantMessage)

    try {
      const eventSource = new EventSource(
        `/api/chat/stream?${new URLSearchParams({
          message: request.message,
          connection_id: String(request.connection_id),
          thread_id: request.thread_id || ''
        })}`
      )

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data)

        switch (data.type) {
          case 'status':
            assistantMessage.content = data.content
            break

          case 'sql':
            assistantMessage.sql = data.content
            break

          case 'result':
            assistantMessage.result = data.content
            assistantMessage.content = `Query executed successfully. Returned ${data.content.row_count} rows.`
            break

          case 'error':
            assistantMessage.error = data.content
            assistantMessage.content = `Error: ${data.content}`
            break

          case 'done':
            currentThreadId.value = data.thread_id
            eventSource.close()
            loading.value = false
            break
        }
      }

      eventSource.onerror = () => {
        eventSource.close()
        assistantMessage.content = 'Error: Connection lost'
        loading.value = false
      }
    } catch (error) {
      assistantMessage.content = 'Error: Failed to start stream'
      loading.value = false
    }
  }

  async function loadConversation(threadId: string) {
    const response = await api.get<{ messages: ChatMessage[] }>(
      `/api/chat/conversations/${threadId}`
    )
    messages.value = response.messages
    currentThreadId.value = threadId
  }

  function clearMessages() {
    messages.value = []
    currentThreadId.value = null
  }

  return {
    messages,
    loading,
    currentThreadId,
    sendMessage,
    sendMessageStream,
    loadConversation,
    clearMessages
  }
}
```

### 2. Main Chat Page (frontend/pages/index.vue)

```vue
<template>
  <div class="flex h-screen bg-gray-50">
    <!-- Sidebar -->
    <ConversationList
      :conversations="conversations"
      @select="handleSelectConversation"
      @new="handleNewChat"
      class="w-64 border-r border-gray-200"
    />

    <!-- Main Chat Area -->
    <div class="flex-1 flex flex-col">
      <!-- Chat Messages -->
      <div class="flex-1 overflow-y-auto p-4 space-y-4">
        <ChatMessage
          v-for="(msg, idx) in messages"
          :key="idx"
          :message="msg"
        />
      </div>

      <!-- Input Area -->
      <div class="border-t border-gray-200 p-4">
        <ChatInput
          :connections="connections"
          :disabled="loading"
          @send="handleSendMessage"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: 'auth'
})

const chat = useChat()
const conversations = useConversations()
const { connections } = useConnections()

const messages = computed(() => chat.messages.value)
const loading = computed(() => chat.loading.value)

onMounted(async () => {
  await conversations.fetchConversations()
  await connections.fetchConnections()
})

function handleSendMessage(data: { message: string; connectionId: number }) {
  chat.sendMessageStream({
    message: data.message,
    connection_id: data.connectionId,
    thread_id: chat.currentThreadId.value || undefined
  })
}

async function handleSelectConversation(threadId: string) {
  await chat.loadConversation(threadId)
}

function handleNewChat() {
  chat.clearMessages()
}
</script>
```

### 3. Chat Message Component (frontend/components/ChatMessage.vue)

```vue
<template>
  <div
    :class="[
      'flex',
      message.role === 'user' ? 'justify-end' : 'justify-start'
    ]"
  >
    <div
      :class="[
        'max-w-3xl rounded-lg p-4',
        message.role === 'user'
          ? 'bg-indigo-600 text-white'
          : 'bg-white border border-gray-200'
      ]"
    >
      <!-- Message Content -->
      <div class="prose prose-sm" v-html="renderMarkdown(message.content)"></div>

      <!-- SQL Display -->
      <SQLDisplay v-if="message.sql" :sql="message.sql" class="mt-3" />

      <!-- Data Table -->
      <DataTable
        v-if="message.result && message.result.rows.length > 0"
        :columns="message.result.columns"
        :rows="message.result.rows"
        class="mt-3"
      />

      <!-- Chart -->
      <DataChart
        v-if="shouldShowChart(message.result)"
        :data="message.result"
        class="mt-3"
      />

      <!-- Error Display -->
      <div
        v-if="message.error"
        class="mt-3 p-3 bg-red-50 border border-red-200 rounded text-red-800 text-sm"
      >
        {{ message.error }}
      </div>

      <!-- Timestamp -->
      <div
        :class="[
          'text-xs mt-2',
          message.role === 'user' ? 'text-indigo-200' : 'text-gray-500'
        ]"
      >
        {{ formatTime(message.timestamp) }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChatMessage } from '~/types/chat'
import { marked } from 'marked'

const props = defineProps<{
  message: ChatMessage
}>()

function renderMarkdown(content: string): string {
  return marked.parse(content)
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString()
}

function shouldShowChart(result: any): boolean {
  if (!result || !result.rows || result.rows.length === 0) return false

  // Show chart if numeric data is present
  const hasNumericColumn = result.columns.some((col: string) => {
    return result.rows.some((row: any[]) => {
      const value = row[result.columns.indexOf(col)]
      return typeof value === 'number'
    })
  })

  return hasNumericColumn && result.rows.length > 1
}
</script>
```

### 4. Data Table Component (frontend/components/DataTable.vue)

```vue
<template>
  <div class="overflow-x-auto">
    <table class="min-w-full divide-y divide-gray-200">
      <thead class="bg-gray-50">
        <tr>
          <th
            v-for="column in columns"
            :key="column"
            class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
          >
            {{ column }}
          </th>
        </tr>
      </thead>
      <tbody class="bg-white divide-y divide-gray-200">
        <tr v-for="(row, idx) in displayRows" :key="idx">
          <td
            v-for="(cell, cellIdx) in row"
            :key="cellIdx"
            class="px-6 py-4 whitespace-nowrap text-sm text-gray-900"
          >
            {{ formatCell(cell) }}
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="rows.length > maxRows" class="mt-2 text-sm text-gray-500 text-center">
      Showing {{ maxRows }} of {{ rows.length }} rows
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  columns: string[]
  rows: any[][]
  maxRows?: number
}>()

const maxRows = computed(() => props.maxRows || 100)

const displayRows = computed(() => {
  return props.rows.slice(0, maxRows.value)
})

function formatCell(value: any): string {
  if (value === null) return 'NULL'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') return value.toLocaleString()
  return String(value)
}
</script>
```

### 5. Data Chart Component (frontend/components/DataChart.vue)

```vue
<template>
  <div class="w-full h-64">
    <canvas ref="chartCanvas"></canvas>
  </div>
</template>

<script setup lang="ts">
import { Chart, registerables } from 'chart.js'
import type { ChartConfiguration } from 'chart.js'

Chart.register(...registerables)

const props = defineProps<{
  data: {
    columns: string[]
    rows: any[][]
  }
}>()

const chartCanvas = ref<HTMLCanvasElement | null>(null)
let chartInstance: Chart | null = null

onMounted(() => {
  if (chartCanvas.value) {
    const config = generateChartConfig(props.data)
    chartInstance = new Chart(chartCanvas.value, config)
  }
})

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.destroy()
  }
})

function generateChartConfig(data: any): ChartConfiguration {
  // Simple bar chart for now
  const labels = data.rows.map((row: any[]) => String(row[0]))
  const values = data.rows.map((row: any[]) => Number(row[1] || 0))

  return {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: data.columns[1] || 'Value',
        data: values,
        backgroundColor: 'rgba(99, 102, 241, 0.5)',
        borderColor: 'rgb(99, 102, 241)',
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'top'
        }
      }
    }
  }
}
</script>
```

### 6. SQL Display Component (frontend/components/SQLDisplay.vue)

```vue
<template>
  <div class="bg-gray-900 rounded-md p-4 overflow-x-auto">
    <div class="flex justify-between items-center mb-2">
      <span class="text-gray-400 text-xs font-mono">SQL</span>
      <button
        @click="copyToClipboard"
        class="text-gray-400 hover:text-white text-xs"
      >
        {{ copied ? 'Copied!' : 'Copy' }}
      </button>
    </div>
    <pre class="text-green-400 font-mono text-sm">{{ sql }}</pre>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  sql: string
}>()

const copied = ref(false)

async function copyToClipboard() {
  await navigator.clipboard.writeText(props.sql)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}
</script>
```

### 7. Chat Input Component (frontend/components/ChatInput.vue)

```vue
<template>
  <div class="space-y-2">
    <div class="flex space-x-2">
      <select
        v-model="selectedConnection"
        class="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
      >
        <option :value="null">Select database...</option>
        <option
          v-for="conn in connections"
          :key="conn.id"
          :value="conn.id"
        >
          {{ conn.name }} ({{ conn.db_type }})
        </option>
      </select>
    </div>

    <div class="flex space-x-2">
      <input
        v-model="message"
        type="text"
        placeholder="Ask a question about your data..."
        :disabled="disabled || !selectedConnection"
        @keydown.enter="handleSend"
        class="flex-1 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
      />
      <button
        @click="handleSend"
        :disabled="disabled || !message.trim() || !selectedConnection"
        class="bg-indigo-600 text-white px-6 py-2 rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Send
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Connection } from '~/types/connection'

const props = defineProps<{
  connections: Connection[]
  disabled?: boolean
}>()

const emit = defineEmits<{
  send: [data: { message: string; connectionId: number }]
}>()

const message = ref('')
const selectedConnection = ref<number | null>(null)

function handleSend() {
  if (!message.value.trim() || !selectedConnection.value) return

  emit('send', {
    message: message.value,
    connectionId: selectedConnection.value
  })

  message.value = ''
}
</script>
```

## Testing & Verification

### Manual Testing Steps

1. **Test basic chat flow**:
   - Login, navigate to home
   - Select database connection
   - Ask: "Show me all users"
   - Verify SQL displayed
   - Verify data table rendered

2. **Test streaming**:
   - Ask complex question
   - Verify status updates during processing
   - Verify results stream in

3. **Test visualizations**:
   - Ask: "Count users by status"
   - Verify chart displays
   - Verify chart type appropriate for data

4. **Test conversation persistence**:
   - Send multiple messages
   - Refresh page
   - Select conversation from sidebar
   - Verify messages loaded

## MCP Browser Testing

```typescript
// Navigate to chat
await navigate_page({ url: 'http://localhost:3000/', type: 'url' })
await take_snapshot()

// Select connection
await click({ uid: 'connection-select' })
await click({ uid: 'connection-option-1' })

// Send message
await fill({ uid: 'message-input', value: 'Show me all users' })
await click({ uid: 'send-button' })

// Wait for response
await wait_for({ text: 'Query executed successfully' })
await take_snapshot()

// Verify SQL displayed
await take_snapshot()

// Verify table rendered
await take_snapshot()
```

## Code Review Checklist

- [ ] SSE streaming works correctly
- [ ] Data tables paginated (max 100 rows displayed)
- [ ] Charts auto-generated for numeric data
- [ ] SQL syntax highlighting applied
- [ ] Copy SQL to clipboard works
- [ ] Messages persist across page refreshes
- [ ] Connection selector required before sending
- [ ] Error messages displayed clearly
- [ ] Loading states prevent double-submission
- [ ] Responsive design on mobile

## Done Criteria

1. Can send chat messages with connection selected
2. SQL displayed with syntax highlighting
3. Data tables render query results
4. Charts auto-generate for numeric data
5. SSE streaming shows real-time status
6. Conversations persist and can be reloaded
7. Sidebar shows conversation history
8. All MCP browser tests pass
9. Responsive on mobile devices

## Rollback Plan

If frontend chat fails:
1. Keep connections UI working
2. Use API docs for testing chat API
3. Revert chat components
4. Frontend phase 09 remains functional
